import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Notification(Base):
    """Durable per-user notification for appointment-lifecycle events.

    Written at the moment the event happens, so it survives the recipient being
    offline or logged out — they read it from the inbox on next login (no
    connectivity needed at event time). An FCM push is attempted in parallel for
    online/backgrounded delivery, but THIS ROW is the source of truth; push is
    best-effort.
    """
    __tablename__ = "notification"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.users.user_uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # appointment_booked | appointment_confirmed | appointment_cancelled
    # | appointment_completed | appointment_no_show
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    appointment_uuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
