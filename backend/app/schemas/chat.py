"""
Chat request/response schemas for the RAG chatbot endpoint.
"""
import uuid
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Patient sends a message to the chatbot."""
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Existing conversation ID for multi-turn chat. Omit to start a new conversation.",
    )


class SourceOut(BaseModel):
    """A single source reference from the RAG retrieval."""
    source: str
    type: str
    name: str
    score: float


class ChatResponse(BaseModel):
    """Full chat response (non-streaming mode)."""
    reply: str
    sources: list[SourceOut]
    conversation_id: uuid.UUID
    language: str
    confidence: float
    is_urgent: bool


class ConversationOut(BaseModel):
    """Conversation summary for listing."""
    id: uuid.UUID
    title: str | None
    language: str
    created_at: str
    message_count: int
    last_message_at: str | None = None
    preview: str | None = None


class MessageOut(BaseModel):
    """A single message in conversation history."""
    id: uuid.UUID
    role: str
    content: str
    sources: list[SourceOut] | None
    confidence: float | None
    created_at: str
