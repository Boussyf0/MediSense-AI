"""
US-15 — Redis Conversation Memory with 24h TTL.

ARCHITECTURE DECISION: Cache-aside pattern
  Redis is a HOT CACHE — the source of truth remains PostgreSQL.
  On every read we check Redis first (fast, O(1)), fall back to DB.
  On every write we update both Redis and DB.

  Why this pattern instead of write-through?
    - If Redis crashes, the DB still has everything.
    - We can wipe Redis anytime and rebuild from DB.
    - No risk of serving stale medical data from cache alone.

KEY DESIGN:
  conversation:{uuid}:meta   → JSON, conversation-level data, TTL=86400s
  conversation:{uuid}:turns  → Redis LIST, each element = one turn JSON, TTL=86400s

  Why a LIST instead of a hash or sorted set?
    - Turns are strictly ordered (time order = insertion order).
    - RPUSH appends, LRANGE retrieves a window → O(n) where n = turns fetched.
    - LLEN gives turn count in O(1).
    - Redis LIST is the natural structure for a chat history.

TTL STRATEGY:
  TTL is reset on every write (EXPIRE after RPUSH).
  → "24h of inactivity", not "24h from first message".
  This matches clinical expectation: a patient mid-consultation should
  never lose context just because the session started 23h ago.

MEMORY ESTIMATION:
  Average turn: ~800 bytes JSON.
  50 turns × 800B = 40KB per conversation.
  500 concurrent patients = 20MB.  → Well within Redis defaults.
"""
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 24 hours in seconds
CONVERSATION_TTL = 86_400


def _redis_url() -> str:
    return settings.REDIS_URL


async def _get_client() -> aioredis.Redis:
    """
    Create a new Redis client for one operation.

    We don't pool at this layer — the security module already uses the same
    REDIS_URL without a shared client, which is fine for low-frequency ops.
    For high-throughput scenarios a shared lifespan client (app.state.redis)
    would be preferred, but that refactor is a Sprint 6+ concern.
    """
    return await aioredis.from_url(
        _redis_url(),
        encoding="utf-8",
        decode_responses=True,
    )


# ── Write ────────────────────────────────────────────────────────────────────


async def push_turn(
    conversation_id: str,
    role: str,           # "user" | "assistant"
    content: str,        # plain-text (Redis stores clear-text; DB stores encrypted)
    context_chunks: list[dict[str, Any]] | None = None,
    confidence: float | None = None,
    message_id: str | None = None,
    created_at: str | None = None,
) -> None:
    """
    Append one conversation turn to Redis and reset the 24h TTL.

    WHY store plain-text in Redis while DB stores encrypted?
      Redis is in-process memory, lives behind the same Docker network,
      and is never exposed to the public internet.  The encryption layer
      in PostgreSQL protects at-rest storage on disk.  Encrypting in Redis
      as well would require the same PGCRYPTO_KEY in the cache layer, adding
      complexity with minimal security gain for this threat model.
      If the security policy changes (e.g. Redis is moved off-host), this
      function is the single place to add AES encryption.

    Args:
        conversation_id : UUID string for the conversation.
        role            : "user" or "assistant".
        content         : Plain-text message content.
        context_chunks  : RAG sources attached to this turn (assistant only).
        confidence      : Retrieval confidence score (assistant only).
        message_id      : Optional DB message UUID, for cache-aside history reads.
        created_at      : Optional ISO datetime, for cache-aside history reads.
    """
    key_turns = f"conversation:{conversation_id}:turns"
    turn = {
        "message_id": message_id,
        "role": role,
        "content": content,
        "context_chunks": context_chunks or [],
        "confidence": confidence,
        "created_at": created_at,
    }
    try:
        redis = await _get_client()
        await redis.rpush(key_turns, json.dumps(turn))
        await redis.expire(key_turns, CONVERSATION_TTL)
        await redis.aclose()
    except Exception as exc:  # pragma: no cover
        # Cache failure MUST NOT break the chat flow — log and continue.
        logger.warning("redis_push_turn_failed conversation=%s err=%s", conversation_id, exc)


async def set_conversation_meta(
    conversation_id: str,
    patient_id: str,
    language: str = "fr",
) -> None:
    """
    Store conversation-level metadata in Redis.

    This allows agents and the DPA summarizer to look up conversation
    context without hitting PostgreSQL.
    """
    key_meta = f"conversation:{conversation_id}:meta"
    meta = {
        "patient_id": patient_id,
        "language": language,
        "conversation_id": conversation_id,
    }
    try:
        redis = await _get_client()
        await redis.set(key_meta, json.dumps(meta), ex=CONVERSATION_TTL)
        await redis.aclose()
    except Exception as exc:  # pragma: no cover
        logger.warning("redis_set_meta_failed conversation=%s err=%s", conversation_id, exc)


# ── Read ─────────────────────────────────────────────────────────────────────


async def get_turns(
    conversation_id: str,
    last_n: int = 10,
) -> list[dict[str, Any]]:
    """
    Retrieve the last N turns from Redis.

    Returns an empty list on any Redis error — callers fall back to DB.

    Args:
        conversation_id : UUID string.
        last_n          : How many most-recent turns to return (default 10).
                          Enough for a multi-turn clinical conversation window
                          without flooding the LLM context.
    """
    key_turns = f"conversation:{conversation_id}:turns"
    try:
        redis = await _get_client()
        # LRANGE with negative index: -last_n to -1 = last N elements
        raw_turns = await redis.lrange(key_turns, -last_n, -1)
        await redis.aclose()
        return [json.loads(t) for t in raw_turns]
    except Exception as exc:
        logger.warning("redis_get_turns_failed conversation=%s err=%s", conversation_id, exc)
        return []


async def get_conversation_meta(conversation_id: str) -> dict[str, Any] | None:
    """Retrieve conversation metadata from Redis. Returns None on miss or error."""
    key_meta = f"conversation:{conversation_id}:meta"
    try:
        redis = await _get_client()
        raw = await redis.get(key_meta)
        await redis.aclose()
        return json.loads(raw) if raw else None
    except Exception as exc:  # pragma: no cover
        logger.warning("redis_get_meta_failed conversation=%s err=%s", conversation_id, exc)
        return None


async def get_turn_count(conversation_id: str) -> int:
    """Return the number of cached turns (O(1) via LLEN)."""
    key_turns = f"conversation:{conversation_id}:turns"
    try:
        redis = await _get_client()
        count = await redis.llen(key_turns)
        await redis.aclose()
        return count
    except Exception:  # pragma: no cover
        logger.warning("Redis LLEN failed for conversation turn count", exc_info=True)
        return 0


# ── Eviction ─────────────────────────────────────────────────────────────────


async def clear_conversation(conversation_id: str) -> None:
    """
    Delete all Redis keys for a conversation.

    Called on:
      1. Explicit user logout (RGPD: right to be forgotten in cache)
      2. Patient account deletion (cascade from DELETE /patient/{uuid})

    Does NOT touch PostgreSQL — DB cleanup is handled by the endpoint.
    """
    key_turns = f"conversation:{conversation_id}:turns"
    key_meta = f"conversation:{conversation_id}:meta"
    try:
        redis = await _get_client()
        await redis.delete(key_turns, key_meta)
        await redis.aclose()
    except Exception as exc:  # pragma: no cover
        logger.warning("redis_clear_failed conversation=%s err=%s", conversation_id, exc)


async def clear_patient_conversations(patient_id: str, conversation_ids: list[str]) -> None:
    """
    Bulk-delete all conversation keys for a patient.

    Called during RGPD account erasure (Art. 17).
    We need the list of conversation_ids because Redis has no native
    "delete by pattern" operation that's safe under load.
    """
    for cid in conversation_ids:
        await clear_conversation(cid)
