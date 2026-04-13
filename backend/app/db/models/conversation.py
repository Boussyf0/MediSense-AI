"""
Conversation and Message models — RGPD-compliant chat storage.

Encryption strategy:
  Message content is encrypted at rest using pgcrypto's pgp_sym_encrypt().
  This satisfies RGPD Article 9 (health data = special category).
  The encryption key is stored in env (PGCRYPTO_KEY), same as Sprint 2 patient data.

Why two tables (not JSONB array)?
  - Individual message queries (search, delete specific messages)
  - Pagination for long conversations
  - Proper foreign key constraints and cascading deletes
  - Audit trail per message (created_at timestamp)
"""
import uuid

from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    ForeignKey,
    DateTime,
    Text,
    LargeBinary,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("secure.patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=True)
    language = Column(String(10), default="fr")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(10), nullable=False)  # 'user' | 'assistant'
    # Content encrypted via pgcrypto — see migration for column_default
    content_encrypted = Column(LargeBinary, nullable=False)
    sources = Column(JSONB, nullable=True)  # [{source, type, name, score}]
    confidence = Column(Float, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
