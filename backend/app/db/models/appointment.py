import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, SmallInteger, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base

if TYPE_CHECKING:
    from .ml_feedback import MLFeedback


class Appointment(Base):
    """
    Appointment model — tracks scheduled visits and no-show predictions.
    Strictly follows the PostgreSQL ERD for Sprint 5.
    """
    __tablename__ = "appointments"
    __table_args__ = {"schema": "public"}

    appointment_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.patients.patient_uuid"), nullable=False
    )
    doctor_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.user_uuid"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(
        SmallInteger, default=20, nullable=False
    )
    
    # Status: PENDING, CONFIRMED, CANCELLED, COMPLETED, NO_SHOW
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False
    )

    # No-show prediction (populated by XGBoost model)
    noshow_probability: Mapped[float | None] = mapped_column(Float)
    noshow_model_ver: Mapped[str | None] = mapped_column(String(20))

    # Triage context (from RAG agent)
    urgency_flag: Mapped[str | None] = mapped_column(String(50))
    urgency_score: Mapped[float | None] = mapped_column(Float)
    rag_summary: Mapped[str | None] = mapped_column(Text)

    # CRM sync
    salesforce_task_id: Mapped[str | None] = mapped_column(String(100))

    # Relationship for MLOps loop (1:0..1)
    ml_feedback: Mapped["MLFeedback"] = relationship(
        "MLFeedback", back_populates="appointment", uselist=False, cascade="all, delete-orphan"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
