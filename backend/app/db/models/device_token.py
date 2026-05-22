import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DeviceToken(Base):
    """FCM registration tokens — one row per (user, device).

    Tokens rotate (Firebase reissues on app reinstall, OS updates, etc.) so we
    upsert by token string and prune duplicates of the same token across users
    on registration.
    """
    __tablename__ = "device_token"
    __table_args__ = (
        UniqueConstraint("token", name="uq_device_token_token"),
        {"schema": "public"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.users.user_uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)  # ios | android | web
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
