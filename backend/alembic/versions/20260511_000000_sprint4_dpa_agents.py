"""Sprint 4 — DPA summaries, agent actions, biometric anomalies tables.

User stories covered:
  US-13: biometric_anomalies table (IoT context injection)
  US-41: dpa_summaries table (Doctor DPA summary view)
  US-42: agent_actions table (Human-in-the-loop approval per action)

Revision ID: 20260511_000000
Revises: 20260427_000000
Create Date: 2026-05-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "20260511_000000"
down_revision = "20260427_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── biometric_anomalies (US-13) ──────────────────────────────────────────
    # Stores IoT sensor anomaly events per patient.
    # In production (Sprint 7) this table will be converted to a TimescaleDB
    # hypertable via: SELECT create_hypertable('biometric_anomalies', 'detected_at');
    op.create_table(
        "biometric_anomalies",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False),
        sa.Column("metric_type", sa.String(30), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("unit", sa.String(10), nullable=True),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Composite index for primary query: last N anomalies per patient
    op.create_index(
        "ix_biometric_anomalies_patient_time",
        "biometric_anomalies",
        ["patient_id", "detected_at"],
    )

    # ── dpa_summaries (US-41 + US-42) ────────────────────────────────────────
    # One row per doctor DPA review session.
    # payload_before = AI output; payload_after = doctor-edited version.
    # version field enables optimistic locking for concurrent approvals.
    op.create_table(
        "dpa_summaries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("doctor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'PENDING'"),
        sa.Column("payload_before", JSONB, nullable=False),
        sa.Column("payload_after", JSONB, nullable=True),
        sa.Column("doctor_note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dpa_summaries_patient", "dpa_summaries", ["patient_id"])
    op.create_index("ix_dpa_summaries_doctor", "dpa_summaries", ["doctor_id"])
    op.create_index("ix_dpa_summaries_status", "dpa_summaries", ["status"])

    # ── agent_actions (US-42) ─────────────────────────────────────────────────
    # Individual recommended actions from a DPA summary.
    # Allows per-action approve/reject/modify decisions.
    op.create_table(
        "agent_actions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "summary_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dpa_summaries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("modified_payload", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_agent_actions_summary", "agent_actions", ["summary_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_actions_summary", table_name="agent_actions")
    op.drop_table("agent_actions")

    op.drop_index("ix_dpa_summaries_status", table_name="dpa_summaries")
    op.drop_index("ix_dpa_summaries_doctor", table_name="dpa_summaries")
    op.drop_index("ix_dpa_summaries_patient", table_name="dpa_summaries")
    op.drop_table("dpa_summaries")

    op.drop_index("ix_biometric_anomalies_patient_time", table_name="biometric_anomalies")
    op.drop_table("biometric_anomalies")
