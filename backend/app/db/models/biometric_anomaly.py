"""
IoT Biometric Anomaly model — early dependency from Sprint 7.

CONTEXT:
  In Sprint 7 we will connect real IoT sensors (SpO2, HR, HRV, temperature)
  via Kafka → TimescaleDB.  That infrastructure doesn't exist yet.

  This model is created NOW because:
    1. US-13 (IoT context in chat) and US-41 (DPA summary) depend on it.
    2. The Alembic migration creates the table in regular PostgreSQL for dev/test.
    3. In production (Sprint 7) we add TimescaleDB hypertable:
         SELECT create_hypertable('biometric_anomalies', 'detected_at');
       TimescaleDB is PostgreSQL-compatible so all queries remain unchanged.

TABLE DESIGN:
  metric_type VARCHAR(30):  'SpO2' | 'HR' | 'HRV' | 'temperature' | ...
    Not ENUM so new sensor types don't require a schema migration.

  severity VARCHAR(10):  'mild' | 'moderate' | 'critical'
    Pre-classified at ingestion time — avoids re-computing on every query.

  No SQLAlchemy FK on patient_id because TimescaleDB (Sprint 7) may live
  on a separate DB node. Referential integrity enforced at application layer.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class BiometricAnomaly(Base):
    __tablename__ = "biometric_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    metric_type = Column(String(30), nullable=False)    # 'SpO2' | 'HR' | 'HRV' | ...
    value = Column(Float, nullable=False)               # raw sensor reading
    threshold = Column(Float, nullable=False)           # threshold that was exceeded
    unit = Column(String(10), nullable=True)            # '%', 'bpm', 'ms', '°C'
    severity = Column(String(10), nullable=False)       # 'mild' | 'moderate' | 'critical'
    source = Column(String(50), nullable=True)          # device/integration identifier
    detected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Primary query: last N anomalies per patient sorted newest-first
        Index("ix_biometric_anomalies_patient_time", "patient_id", "detected_at"),
    )

    def to_context_dict(self) -> dict[str, Any]:
        """
        Serialize this anomaly as a context dict for the RAG pipeline.

        The format is designed to be readable by the LLM as plain-text context,
        similar to how RAG chunks are injected into the prompt.
        """
        unit: str = self.unit or ""           # type: ignore[assignment]
        detected_at: datetime | None = self.detected_at  # type: ignore[assignment]
        return {
            "metric": self.metric_type,
            "value": self.value,
            "unit": unit,
            "threshold": self.threshold,
            "severity": self.severity,
            "source": self.source or "sensor",  # type: ignore[operator]
            "detected_at": detected_at.isoformat() if detected_at else None,
        }
