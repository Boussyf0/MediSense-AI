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
