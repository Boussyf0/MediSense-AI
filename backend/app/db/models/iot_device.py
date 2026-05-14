import uuid
from datetime import datetime
from sqlalchemy import Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class IotDevice(Base):
    __tablename__ = "iot_device"
    __table_args__ = {"schema": "public"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.patients.patient_uuid"),
        unique=True,
        nullable=False,
    )
    paired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    battery: Mapped[int | None] = mapped_column(Integer, nullable=True)
