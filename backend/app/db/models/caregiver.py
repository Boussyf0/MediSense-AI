import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base

class PatientCaregiver(Base):
    """
    Links a patient to a caregiver. 
    A patient can have multiple caregivers, and a caregiver can monitor multiple patients.
    Status can be 'pending' (invited but not accepted), 'accepted', or 'rejected'.
    """
    __tablename__ = "patient_caregivers"
    __table_args__ = (
        PrimaryKeyConstraint("patient_uuid", "caregiver_uuid"),
        {"schema": "public"},
    )

    patient_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.patients.patient_uuid"), nullable=False
    )
    caregiver_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public.users.user_uuid"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
