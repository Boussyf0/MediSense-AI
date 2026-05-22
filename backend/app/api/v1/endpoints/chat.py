"""
Chat endpoint — RAG-powered medical chatbot.

Routes:
  POST /chat          Send a message → JSON ChatResponse
  POST /chat/stream   Send a message → SSE stream (text/event-stream)
  GET  /chat          List patient's conversations
  GET  /chat/{id}     Get conversation history (decrypted)
  DELETE /chat/{id}   Delete a conversation (RGPD Art. 17 — right to erasure)

Two separate endpoints for JSON vs SSE so that OpenAPI/Swagger correctly
documents each route's response schema (ChatResponse vs event stream).
"""
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AgentRoute, run_agent_flow
from app.db.session import get_db
from app.core.config import get_settings
from app.core.conversation_cache import (
    clear_conversation,
    get_turns,
    push_turn,
    set_conversation_meta,
)
from app.core.dependencies import TokenPayload, require_patient
from app.db.models.conversation import Conversation
from app.db.models.patient import Patient
from app.api.v1.endpoints.metrics import active_conversations
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceOut,
    ConversationOut,
    MessageOut,
)
from app.rag.pipeline import run, run_stream

router = APIRouter(prefix="/chat", tags=["Chat (RAG)"])
settings = get_settings()


@router.post("", response_model=ChatResponse, summary="Send message (JSON response)")
async def send_message(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
):
    """
    Send a message to the MediSense chatbot. Returns a complete JSON response.

    - If `conversation_id` is provided, continues an existing conversation.
    - Otherwise, creates a new conversation.
    - For token-by-token streaming use `POST /chat/stream` instead.
    """
    active_conversations.inc()
    try:
        patient_id = uuid.UUID(current_user.sub)
        await _ensure_patient_profile_exists(db, patient_id)

        # Resolve or create conversation
        if body.conversation_id:
            conv = await _get_conversation(db, body.conversation_id, patient_id)
        else:
            conv = Conversation(patient_id=patient_id)
            db.add(conv)
            await db.flush()

        # Non-streaming path
        result = await run(
            body.message,
            patient_id=str(patient_id),
            db=db,
        )
        agent_result = await run_agent_flow(
            query_fr=result.query_fr,
            patient_id=str(patient_id),
            conversation_id=str(conv.id),
            iot_anomalies=result.iot_context.anomalies if result.iot_context else [],
            is_urgent_from_rag=result.is_urgent,
            db=db,
        )
        final_reply = _merge_agent_message(
            result.reply,
            agent_result.chat_message if agent_result.route != AgentRoute.INFO else "",
        )
        final_is_urgent = result.is_urgent or agent_result.route == AgentRoute.ESCALATE

        # Auto-generate title from first message
        if not conv.title:
            conv.title = body.message[:80]

        conv.language = result.language
        await set_conversation_meta(str(conv.id), str(patient_id), result.language)
        sources_out = [SourceOut(**s) for s in result.sources]

        # Persist user message (encrypted)
        user_msg_id, user_created_at = await _save_message(db, conv.id, "user", body.message)
        await push_turn(
            conversation_id=str(conv.id),
            role="user",
            content=body.message,
            message_id=str(user_msg_id),
            created_at=user_created_at,
        )

        # Persist assistant reply (encrypted)
        assistant_msg_id, assistant_created_at = await _save_message(
            db,
            conv.id,
            "assistant",
            final_reply,
            sources=[{"source": s.source, "type": s.type, "name": s.name, "score": s.score} for s in sources_out],
            confidence=result.confidence,
        )
        await push_turn(
            conversation_id=str(conv.id),
            role="assistant",
            content=final_reply,
            context_chunks=[{"source": s.source, "type": s.type, "name": s.name, "score": s.score} for s in sources_out],
            confidence=result.confidence,
            message_id=str(assistant_msg_id),
            created_at=assistant_created_at,
        )

        await db.commit()

        return ChatResponse(
            reply=final_reply,
            sources=sources_out,
            conversation_id=conv.id,
            language=result.language,
            confidence=result.confidence,
            is_urgent=final_is_urgent,
        )
    finally:
        active_conversations.dec()


@router.post(
    "/stream",
    summary="Send message (SSE streaming)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-Sent Events stream. Each event is a JSON object.",
            "content": {
                "text/event-stream": {
                    "example": (
                        'data: {"type": "lang", "value": "darija"}\n\n'
                        'data: {"type": "sources", "value": [...]}\n\n'
                        'data: {"type": "token", "value": "Selon"}\n\n'
                        'data: {"type": "done", "confidence": 0.82}\n\n'
                    )
                }
            },
        }
    },
)
async def send_message_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
):
    """
    Send a message and receive the response as Server-Sent Events (SSE).

    The response is a unidirectional server→client stream. The client sends
    one POST request; the server streams tokens as they are generated by
    Mistral 7B. Time-to-first-token is typically < 200ms.

    Event types:
    - `lang`    — detected language ("fr" | "ar" | "darija")
    - `sources` — list of retrieved chunks used as context
    - `token`   — one text token from the LLM
    - `done`    — final event with confidence score and conversation_id
    """
    patient_id = uuid.UUID(current_user.sub)
    await _ensure_patient_profile_exists(db, patient_id)

    if body.conversation_id:
        conv = await _get_conversation(db, body.conversation_id, patient_id)
    else:
        conv = Conversation(patient_id=patient_id, title=body.message[:80])
        db.add(conv)
        await db.flush()
    await set_conversation_meta(str(conv.id), str(patient_id), conv.language or "fr")

    return StreamingResponse(
        _stream_response(body.message, conv, patient_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List the patient's conversations (newest activity first)."""
    patient_id = uuid.UUID(current_user.sub)

    stmt = text("""
        SELECT
            c.id,
            c.title,
            c.language,
            c.created_at,
            COALESCE(m_stats.cnt, 0) AS message_count,
            m_last.created_at AS last_message_at,
            CASE
                WHEN m_last.content_encrypted IS NOT NULL
                THEN pgp_sym_decrypt(m_last.content_encrypted, :key)
                ELSE NULL
            END AS preview
        FROM conversations c
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id = c.id
        ) m_stats ON TRUE
        LEFT JOIN LATERAL (
            SELECT content_encrypted, created_at
            FROM messages
            WHERE conversation_id = c.id
            ORDER BY created_at DESC
            LIMIT 1
        ) m_last ON TRUE
        WHERE c.patient_id = :patient_id
        ORDER BY COALESCE(m_last.created_at, c.created_at) DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(
        stmt,
        {
            "patient_id": patient_id,
            "key": settings.PGCRYPTO_KEY,
            "limit": limit,
            "offset": offset,
        },
    )
    rows = result.all()

    def _truncate(text_val: str | None, max_len: int = 140) -> str | None:
        if not text_val:
            return None
        cleaned = text_val.strip().replace("\n", " ")
        return cleaned if len(cleaned) <= max_len else cleaned[: max_len - 1] + "…"

    return [
        ConversationOut(
            id=row.id,
            title=row.title,
            language=row.language,
            created_at=row.created_at.isoformat(),
            message_count=row.message_count,
            last_message_at=row.last_message_at.isoformat() if row.last_message_at else None,
            preview=_truncate(row.preview),
        )
        for row in rows
    ]


@router.get("/{conversation_id}", response_model=list[MessageOut])
async def get_conversation_history(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
):
    """Get all messages in a conversation (decrypted)."""
    patient_id = uuid.UUID(current_user.sub)
    conv = await _get_conversation(db, conversation_id, patient_id)
    cached_turns = await get_turns(str(conversation_id), last_n=2000)
    cached_messages = _cache_turns_to_messages(cached_turns)
    if cached_messages:
        return cached_messages
    if cached_turns and cached_messages is None:
        await clear_conversation(str(conversation_id))

    # Decrypt messages using pgcrypto
    stmt = text("""
        SELECT id, role,
               pgp_sym_decrypt(content_encrypted, :key) AS content,
               sources, confidence, created_at
        FROM messages
        WHERE conversation_id = :conv_id
        ORDER BY created_at ASC
    """)

    result = await db.execute(stmt, {"key": settings.PGCRYPTO_KEY, "conv_id": conv.id})
    rows = result.all()

    messages = [
        MessageOut(
            id=row.id,
            role=row.role,
            content=row.content,
            sources=[SourceOut(**s) for s in row.sources] if row.sources else None,
            confidence=row.confidence,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
    await set_conversation_meta(str(conv.id), str(patient_id), conv.language or "fr")
    for msg in messages:
        await push_turn(
            conversation_id=str(conv.id),
            role=msg.role,
            content=msg.content,
            context_chunks=[s.model_dump() for s in msg.sources] if msg.sources else [],
            confidence=msg.confidence,
            message_id=str(msg.id),
            created_at=msg.created_at,
        )
    return messages


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
):
    """
    Delete a conversation and all its messages.

    RGPD Article 17 — Right to erasure: patients can delete their chat history.
    CASCADE delete removes all messages automatically.
    """
    patient_id = uuid.UUID(current_user.sub)
    conv = await _get_conversation(db, conversation_id, patient_id)
    await db.delete(conv)
    await db.commit()
    await clear_conversation(str(conversation_id))


# ── Helpers ──────────────────────────────────────────────


async def _get_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    patient_id: uuid.UUID,
) -> Conversation:
    """Fetch a conversation, verifying ownership."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.patient_id == patient_id,
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


async def _ensure_patient_profile_exists(db: AsyncSession, patient_id: uuid.UUID) -> None:
    """Fail fast with a clear error when JWT subject has no patient profile."""
    result = await db.execute(
        select(Patient.patient_uuid).where(Patient.patient_uuid == patient_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")


async def _save_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    sources: list[dict] | None = None,
    confidence: float | None = None,
) -> tuple[uuid.UUID, str]:
    """Save an encrypted message to the database and return its ID + timestamp."""
    stmt = text("""
        INSERT INTO messages (id, conversation_id, role, content_encrypted, sources, confidence)
        VALUES (
            gen_random_uuid(),
            :conv_id,
            :role,
            pgp_sym_encrypt(:content, :key),
            :sources,
            :confidence
        )
        RETURNING id, created_at
    """)
    result = await db.execute(
        stmt,
        {
            "conv_id": conversation_id,
            "role": role,
            "content": content,
            "key": settings.PGCRYPTO_KEY,
            "sources": json.dumps(sources) if sources else None,
            "confidence": confidence,
        },
    )
    row = result.fetchone()
    if not row:
        raise RuntimeError("Failed to persist chat message")
    created_at: datetime = row.created_at
    return row.id, created_at.isoformat()


async def _stream_response(
    message: str,
    conv: Conversation,
    patient_id: uuid.UUID,
    db: AsyncSession,
):
    """SSE event generator for streaming chat responses."""
    full_reply = ""
    sources_data = []
    confidence = 0.0
    is_urgent_from_rag = False
    iot_anomalies: list[dict] = []
    done_event: dict | None = None

    async for event in run_stream(message, patient_id=str(patient_id), db=db):
        event_type = event.get("type", "")

        if event_type == "lang":
            conv.language = event["value"]
            yield f"data: {json.dumps(event)}\n\n"

        elif event_type == "iot":
            iot_val = event.get("value", [])
            iot_anomalies = iot_val if isinstance(iot_val, list) else []
            yield f"data: {json.dumps(event)}\n\n"

        elif event_type == "sources":
            sources_data = event["value"]
            yield f"data: {json.dumps(event)}\n\n"

        elif event_type == "token":
            full_reply += event["value"]
            yield f"data: {json.dumps(event)}\n\n"

        elif event_type == "done":
            confidence = event.get("confidence", 0.0)
            is_urgent_from_rag = bool(event.get("is_urgent", False))
            done_event = event

    # Persist after streaming completes
    if not conv.title:
        conv.title = message[:80]
    await set_conversation_meta(str(conv.id), str(patient_id), conv.language or "fr")
    agent_result = await run_agent_flow(
        query_fr=message,
        patient_id=str(patient_id),
        conversation_id=str(conv.id),
        iot_anomalies=iot_anomalies,
        is_urgent_from_rag=is_urgent_from_rag,
        db=db,
    )
    merged_reply = _merge_agent_message(
        full_reply,
        agent_result.chat_message if agent_result.route != AgentRoute.INFO else "",
    )
    if merged_reply != full_reply:
        extra = merged_reply[len(full_reply):]
        if extra:
            yield f"data: {json.dumps({'type': 'token', 'value': extra})}\n\n"
    full_reply = merged_reply

    user_msg_id, user_created_at = await _save_message(db, conv.id, "user", message)
    await push_turn(
        conversation_id=str(conv.id),
        role="user",
        content=message,
        message_id=str(user_msg_id),
        created_at=user_created_at,
    )
    assistant_msg_id, assistant_created_at = await _save_message(
        db,
        conv.id,
        "assistant",
        full_reply,
        sources_data,
        confidence,
    )
    await push_turn(
        conversation_id=str(conv.id),
        role="assistant",
        content=full_reply,
        context_chunks=sources_data,
        confidence=confidence,
        message_id=str(assistant_msg_id),
        created_at=assistant_created_at,
    )
    await db.commit()
    final_is_urgent = is_urgent_from_rag or agent_result.route == AgentRoute.ESCALATE
    final_done = done_event or {"type": "done", "confidence": confidence}
    final_done["is_urgent"] = final_is_urgent
    yield f"data: {json.dumps({**final_done, 'conversation_id': str(conv.id)})}\n\n"


def _merge_agent_message(base_reply: str, agent_message: str) -> str:
    """Append orchestrator output while preserving the RAG reply."""
    if not agent_message:
        return base_reply
    if base_reply and agent_message in base_reply:
        return base_reply
    if not base_reply:
        return agent_message
    return f"{base_reply}\n\n{agent_message}"


def _cache_turns_to_messages(cached_turns: list[dict]) -> list[MessageOut] | None:
    """
    Convert cached turns to API response models.

    Returns None when cache entries are incomplete/corrupted so caller can fall
    back to PostgreSQL and repopulate the cache.
    """
    if not cached_turns:
        return []
    messages: list[MessageOut] = []
    try:
        for turn in cached_turns:
            msg_id = turn.get("message_id")
            created_at = turn.get("created_at")
            if not msg_id or not created_at:
                return None
            messages.append(
                MessageOut(
                    id=uuid.UUID(str(msg_id)),
                    role=str(turn.get("role", "")),
                    content=str(turn.get("content", "")),
                    sources=[SourceOut(**s) for s in turn.get("context_chunks", [])] if turn.get("context_chunks") else None,
                    confidence=turn.get("confidence"),
                    created_at=str(created_at),
                )
            )
    except (ValueError, TypeError, KeyError, ValidationError):
        return None
    return messages
