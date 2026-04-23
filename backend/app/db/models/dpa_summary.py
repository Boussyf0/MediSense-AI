"""
DPA Summary model — US-41 (Doctor DPA view) + US-42 (Human-in-the-Loop).

DPA = Decision-support Panel for doctors (Aide à la Décision du Praticien).

TWO TABLES:

1. dpa_summaries — one row per doctor review session
   Stores the full AI-generated summary (symptoms + IoT + recommended actions)
   and the doctor's approval decision.

   STATUS lifecycle:
     PENDING  → doctor has not yet reviewed
     APPROVED → doctor accepted the AI recommendations
     MODIFIED → doctor edited one or more recommendations before approving
     REJECTED → doctor rejected the AI recommendations (feedback for retraining)

   Why store payload_before AND payload_after?
     Medical audit trail requirement (RGPD Art. 35 — high-risk AI systems).
     We must be able to reconstruct exactly what the AI suggested and what
     the doctor changed. "payload_before" = AI output, "payload_after" = doctor
     edit, or identical to payload_before if no changes were made.

2. agent_actions — one row per recommended action within a DPA summary
   Normalizes the recommended_actions array so each action can be individually
   approved/rejected. Avoids re-parsing JSONB on every approval operation.

   action_type : 'prescribe' | 'monitor' | 'refer' | 'book' | 'alert'
   status      : 'pending' | 'approved' | 'rejected' | 'modified'

OPTIMISTIC LOCKING (version field on dpa_summaries):
  Prevents two doctors from approving the same summary simultaneously.
  Workflow:
    1. Doctor A reads summary → version=1
    2. Doctor B reads summary → version=1
    3. Doctor A approves → UPDATE ... WHERE id=? AND version=1 → version=2 ✓
    4. Doctor B approves → UPDATE ... WHERE id=? AND version=1 → 0 rows updated
       → API returns HTTP 409 Conflict → Doctor B must refresh and re-review.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class DPASummary(Base):
    __tablename__ = "dpa_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # set on approval

    # Optimistic locking — incremented on each state change
    version = Column(Integer, nullable=False, default=1)

    # Status: PENDING → APPROVED | MODIFIED | REJECTED
    status = Column(String(20), nullable=False, default="PENDING")

    # Full AI-generated payload (symptoms + IoT + recommended_actions + confidence)
    payload_before = Column(JSONB, nullable=False)
    # Doctor-edited payload (same as payload_before if no edits)
    payload_after = Column(JSONB, nullable=True)

    # Doctor's free-text comment (optional — why they rejected or what they changed)
    doctor_note = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to individual action rows
    actions = relationship(
        "AgentAction",
        back_populates="summary",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AgentAction(Base):
    """
    Individual recommended action from a DPA summary.

    Each row represents one entry in the 'recommended_actions' array.
    Doctors can approve/reject individual actions, not just the whole summary.
    """
    __tablename__ = "agent_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    summary_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dpa_summaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Action details
    action_type = Column(String(20), nullable=False)  # 'prescribe'|'monitor'|'refer'|...
    payload = Column(JSONB, nullable=False)            # original AI action payload
    modified_payload = Column(JSONB, nullable=True)   # doctor-edited payload (if any)

    # Decision
    status = Column(String(20), nullable=False, default="pending")
    # 'pending' | 'approved' | 'rejected' | 'modified'

    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(UUID(as_uuid=True), nullable=True)  # doctor UUID

    summary = relationship("DPASummary", back_populates="actions")
