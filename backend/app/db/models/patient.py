"""
Patient models — pseudonymized by design (RGPD Art. 25).

Two separate tables:
  - Patient: UUID + ML features + consent flags (no civil identity)
  - PatientIdentity: encrypted civil data (separate secure schema)

The application NEVER joins these two tables in normal operations.
Only the RGPD DPO endpoint can perform the de-pseudonymization join.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, SmallInteger, ARRAY, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class Patient(Base):
    """Public pseudonymized patient record — UUID only, no civil identity."""
    __tablename__ = "patients"
    __table_args__ = {"schema": "public"}

    patient_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Granular consent (RGPD Art. 7)
    consent_iot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_nlp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_sharing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Demographics for ML — never enough to re-identify alone
    birth_year: Mapped[int | None] = mapped_column(SmallInteger)
    sex: Mapped[str | None] = mapped_column(String(1))
    city_code: Mapped[str | None] = mapped_column(String(10))
    chronic_conditions: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PatientIdentity(Base):
    """
    Civil identity stored encrypted in the secure schema.

    All fields stored as BYTEA encrypted with pgcrypto.
    Decryption only happens in the DPO endpoint, never in normal API flows.

    The encryption/decryption key (PGCRYPTO_KEY) comes from environment —
    it is NEVER stored in the database.
    """
    __tablename__ = "patients_identity"
    __table_args__ = {"schema": "secure"}

    patient_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    # Encrypted fields — stored as bytea, decrypted only when explicitly needed
    full_name_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    phone_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    email_enc: Mapped[bytes | None] = mapped_column(LargeBinary)

    # Consent timestamps
    consent_iot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_nlp_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_sharing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cgu_version: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
