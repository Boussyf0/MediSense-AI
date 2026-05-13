import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class SmsReminderLog(Base):
    __tablename__ = "sms_reminder_log"
    __table_args__ = {"schema": "public"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.appointments.appointment_uuid"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(40), nullable=False, default="sms_reminder")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
