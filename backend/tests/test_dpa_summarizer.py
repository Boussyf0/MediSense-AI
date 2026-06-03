"""
Regression tests for the DPA summarizer persistence logic.

Catches the bug where AgentAction rows were inserted with summary_id=NULL
because Column(default=uuid.uuid4) on DPASummary.id only fires at INSERT
time, so summary.id was still None when the action rows were built.
"""
import uuid

import pytest
from sqlalchemy import select

from app.db.models.dpa_summary import AgentAction, DPASummary
from app.services import dpa_summarizer


@pytest.mark.asyncio
async def test_build_persists_actions_with_summary_id(test_db):
    """Building a DPA must produce AgentAction rows linked to the summary."""
    patient_id = str(uuid.uuid4())
    doctor_id = str(uuid.uuid4())

    summary = await dpa_summarizer.build(
        patient_id=patient_id,
        db=test_db,
        doctor_id=doctor_id,
    )

    assert summary.id is not None

    actions = (
        await test_db.execute(
            select(AgentAction).where(AgentAction.summary_id == summary.id)
        )
    ).scalars().all()

    assert len(actions) >= 1, "default rule-based recommendation should produce >=1 action"
    for action in actions:
        assert action.summary_id == summary.id
        assert action.status == "pending"
        assert action.action_type


@pytest.mark.asyncio
async def test_build_returns_persisted_summary(test_db):
    """The returned summary must be retrievable by id from the DB."""
    patient_id = str(uuid.uuid4())

    summary = await dpa_summarizer.build(
        patient_id=patient_id,
        db=test_db,
        doctor_id=None,
    )

    fetched = (
        await test_db.execute(
            select(DPASummary).where(DPASummary.id == summary.id)
        )
    ).scalar_one()

    assert fetched.patient_id == uuid.UUID(patient_id)
    assert fetched.status == "PENDING"
    assert fetched.payload_before["recommended_actions"]


# ── Direct tests for async helper functions ─────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_iot_summary_empty(test_db):
    """No anomalies → stable trend and empty list."""
    patient_id = uuid.uuid4()
    result = await dpa_summarizer._fetch_iot_summary(patient_id, test_db)
    assert result["trend"] == "stable"
    assert result["latest_anomalies"] == []


@pytest.mark.asyncio
async def test_fetch_iot_summary_with_anomalies(test_db):
    """Anomalies present → populates latest_anomalies and computes trend."""
    from datetime import datetime, timezone
    from app.db.models.biometric_anomaly import BiometricAnomaly

    patient_id = uuid.uuid4()
    for i, (metric, sev, val) in enumerate([
        ("SpO2", "critical", 88.0),
        ("HR", "moderate", 110.0),
        ("SpO2", "mild", 94.0),
    ]):
        test_db.add(BiometricAnomaly(
            patient_id=patient_id,
            metric_type=metric,
            value=val,
            threshold=95.0 if metric == "SpO2" else 100.0,
            unit="%" if metric == "SpO2" else "bpm",
            severity=sev,
            detected_at=datetime(2026, 5, 20 + i, 10, 0, tzinfo=timezone.utc),
        ))
    await test_db.flush()

    result = await dpa_summarizer._fetch_iot_summary(patient_id, test_db)
    assert len(result["latest_anomalies"]) >= 1
    assert result["trend"] == "critical"  # critical in last 3


@pytest.mark.asyncio
async def test_fetch_recent_symptoms_empty(test_db):
    """No conversations → empty symptoms list."""
    patient_id = uuid.uuid4()
    result = await dpa_summarizer._fetch_recent_symptoms(patient_id, test_db)
    # Returns ([], False) or [] depending on implementation
    if isinstance(result, tuple):
        symptoms, is_urgent = result
    else:
        symptoms = result
    assert symptoms == []


@pytest.mark.asyncio
async def test_fetch_iot_summary_db_error(test_db):
    """DB error → returns safe default."""
    from unittest.mock import AsyncMock
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("DB down"))

    patient_id = uuid.uuid4()
    result = await dpa_summarizer._fetch_iot_summary(patient_id, mock_db)
    assert result["trend"] == "stable"
    assert result["latest_anomalies"] == []


@pytest.mark.asyncio
async def test_decrypt_message_no_pgcrypto(test_db):
    """decrypt_message with non-existent message → returns None."""
    msg_id = uuid.uuid4()
    result = await dpa_summarizer._decrypt_message(msg_id, test_db)
    assert result is None
