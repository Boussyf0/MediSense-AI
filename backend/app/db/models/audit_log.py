"""
Audit log models — maps to existing tables created in init_db.sql.

Two immutable tables (enforced by DB-level rules in init_db.sql):
  - AuditLog     : RGPD Art. 30 — every access to patient data is logged
  - ConsentLog   : RGPD Art. 7  — every consent change is logged

WHY IMMUTABLE?
  Medical regulations require that audit trails cannot be tampered with.
  The PostgreSQL RULE prevents any UPDATE or DELETE at the DB level,
  so even a bug in application code can't corrupt the audit history.

WHY BIGSERIAL (int) and not UUID for PK?
  These tables are append-only and queried in time order.
  Sequential integer PKs give better index locality for range scans
  (e.g., "get all logs between date A and date B").
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class AuditLog(Base):
    """
    Immutable record of every access to patient data.

    Written by every endpoint that reads, writes, exports, or deletes
    patient-related resources. The DB-level RULE prevents modification.

    Action vocabulary (RGPD Art. 30):
      READ       — endpoint read patient data
      WRITE      — endpoint created or modified patient data
      DELETE     — endpoint soft-deleted or anonymized patient data
      EXPORT     — patient requested their full data export (Art. 20)
      CONSENT    — consent flags were updated
      LOGIN      — authentication event
    """
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))    # max IPv6 length = 45 chars
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ConsentLog(Base):
    """
    Immutable record of every consent change.

    Separate from AuditLog because consent history has a specific
    legal meaning (RGPD Art. 7) and needs its own query patterns
    (e.g., "show me all consent changes for patient X").

    consent_type : 'iot' | 'nlp' | 'sharing'
    action       : 'granted' | 'revoked'
    channel      : 'app' | 'web' | 'paper'
    """
    __tablename__ = "consent_logs"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    patient_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)   # 'granted' | 'revoked'
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    cgu_version: Mapped[str | None] = mapped_column(String(20))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
