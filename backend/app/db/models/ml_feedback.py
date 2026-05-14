import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base

if TYPE_CHECKING:
    from .appointment import Appointment


class MLFeedback(Base):
    """
    ML Feedback model — closes the MLOps loop for retraining.
    Captures ground truth for no-show predictions.
    """
    __tablename__ = "ml_feedback"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    appointment_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.appointments.appointment_uuid"), unique=True, nullable=False
    )
    
    # Ground truth (was the prediction correct?)
    was_predicted_correctly: Mapped[bool | None] = mapped_column(Boolean)
    actual_status: Mapped[str] = mapped_column(String(20), nullable=False) # e.g., COMPLETED vs NO_SHOW
    
    # MLOps metadata
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    prediction_prob: Mapped[float] = mapped_column(nullable=False)
    
    # Optional doctor feedback
    doctor_feedback: Mapped[str | None] = mapped_column(String(500))

    # Relationship back to appointment
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="ml_feedback"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
