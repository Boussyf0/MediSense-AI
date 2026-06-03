"""
Tests for conversation cache (Redis-backed) — Sprint 3 (US-15).

All tests mock Redis to avoid needing a live Redis instance.
Tests cover: push_turn, set_conversation_meta, get_turns,
get_conversation_meta, get_turn_count, clear_conversation,
clear_patient_conversations.
"""
import json
from unittest.mock import AsyncMock, patch

from app.core.conversation_cache import (
    CONVERSATION_TTL,
    clear_conversation,
    clear_patient_conversations,
    get_conversation_meta,
    get_turn_count,
    get_turns,
    push_turn,
    set_conversation_meta,
)


def _mock_redis():
    """Create a mock Redis client with common operations."""
    r = AsyncMock()
    r.rpush = AsyncMock()
    r.expire = AsyncMock()
    r.set = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.lrange = AsyncMock(return_value=[])
    r.llen = AsyncMock(return_value=0)
    r.delete = AsyncMock()
    r.aclose = AsyncMock()
    return r


@patch("app.core.conversation_cache._get_client")
async def test_push_turn(mock_get_client):
    """push_turn appends to Redis list and sets TTL."""
    redis = _mock_redis()
    mock_get_client.return_value = redis

    await push_turn("conv-123", "user", "Bonjour")

    redis.rpush.assert_awaited_once()
    call_args = redis.rpush.call_args
    assert call_args[0][0] == "conversation:conv-123:turns"
    turn_data = json.loads(call_args[0][1])
    assert turn_data["role"] == "user"
    assert turn_data["content"] == "Bonjour"
    redis.expire.assert_awaited_once_with(
        "conversation:conv-123:turns", CONVERSATION_TTL
    )
    redis.aclose.assert_awaited_once()


@patch("app.core.conversation_cache._get_client")
async def test_set_conversation_meta(mock_get_client):
    """set_conversation_meta stores JSON metadata with TTL."""
    redis = _mock_redis()
    mock_get_client.return_value = redis

    await set_conversation_meta("conv-456", "patient-abc", language="fr")

    redis.set.assert_awaited_once()
    call_args = redis.set.call_args
    assert call_args[0][0] == "conversation:conv-456:meta"
    meta = json.loads(call_args[0][1])
    assert meta["patient_id"] == "patient-abc"
    assert meta["language"] == "fr"
    redis.aclose.assert_awaited_once()


@patch("app.core.conversation_cache._get_client")
async def test_get_turns_returns_parsed_json(mock_get_client):
    """get_turns returns parsed turn dicts from Redis list."""
    redis = _mock_redis()
    turn1 = json.dumps({"role": "user", "content": "Salut"})
    turn2 = json.dumps({"role": "assistant", "content": "Bonjour!"})
    redis.lrange = AsyncMock(return_value=[turn1, turn2])
    mock_get_client.return_value = redis

    turns = await get_turns("conv-789", last_n=10)

    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["content"] == "Bonjour!"
    redis.aclose.assert_awaited_once()


@patch("app.core.conversation_cache._get_client")
async def test_get_turns_empty(mock_get_client):
    """get_turns with no cached turns → empty list."""
    redis = _mock_redis()
    mock_get_client.return_value = redis

    turns = await get_turns("conv-empty")
    assert turns == []


@patch("app.core.conversation_cache._get_client")
async def test_get_turns_redis_error_returns_empty(mock_get_client):
    """Redis failure → empty list (graceful degradation)."""
    mock_get_client.side_effect = ConnectionError("Redis down")

    turns = await get_turns("conv-fail")
    assert turns == []


@patch("app.core.conversation_cache._get_client")
async def test_get_conversation_meta(mock_get_client):
    """get_conversation_meta returns parsed metadata."""
    redis = _mock_redis()
    meta = {"patient_id": "p-123", "language": "fr", "conversation_id": "conv-111"}
    redis.get = AsyncMock(return_value=json.dumps(meta))
    mock_get_client.return_value = redis

    result = await get_conversation_meta("conv-111")

    assert result is not None
    assert result["patient_id"] == "p-123"
    redis.aclose.assert_awaited_once()


@patch("app.core.conversation_cache._get_client")
async def test_get_conversation_meta_miss(mock_get_client):
    """Cache miss → returns None."""
    redis = _mock_redis()
    redis.get = AsyncMock(return_value=None)
    mock_get_client.return_value = redis

    result = await get_conversation_meta("conv-missing")
    assert result is None


@patch("app.core.conversation_cache._get_client")
async def test_get_turn_count(mock_get_client):
    """get_turn_count returns LLEN result."""
    redis = _mock_redis()
    redis.llen = AsyncMock(return_value=7)
    mock_get_client.return_value = redis

    count = await get_turn_count("conv-count")

    assert count == 7
    redis.llen.assert_awaited_once_with("conversation:conv-count:turns")
    redis.aclose.assert_awaited_once()


@patch("app.core.conversation_cache._get_client")
async def test_clear_conversation(mock_get_client):
    """clear_conversation deletes both turns and meta keys."""
    redis = _mock_redis()
    mock_get_client.return_value = redis

    await clear_conversation("conv-del")

    redis.delete.assert_awaited_once_with(
        "conversation:conv-del:turns",
        "conversation:conv-del:meta",
    )
    redis.aclose.assert_awaited_once()


@patch("app.core.conversation_cache._get_client")
async def test_clear_patient_conversations(mock_get_client):
    """Bulk-clear deletes keys for each conversation."""
    redis = _mock_redis()
    mock_get_client.return_value = redis

    await clear_patient_conversations("patient-xyz", ["c1", "c2", "c3"])

    assert redis.delete.await_count == 3
