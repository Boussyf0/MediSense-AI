"""
Tests for Sprint 2 patient endpoints.

US-06  PATCH /patients/{uuid}/consent   — granular consent update
US-07  GET   /patients/{uuid}/data/export — RGPD data portability
US-08  DELETE /patients/{uuid}           — right to erasure
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models.conversation import Conversation
from app.db.models.patient import Patient, PatientIdentity
from app.db.models.audit_log import AuditLog, ConsentLog


# ── Helpers ───────────────────────────────────────────────

def doctor_token() -> str:
    return create_access_token(subject=str(uuid.uuid4()), role="doctor")

def admin_token() -> str:
    return create_access_token(subject=str(uuid.uuid4()), role="admin")

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def seed_patient(db: AsyncSession, **kwargs) -> Patient:
    """Insert a minimal patient row into the test DB."""
    patient = Patient(
        consent_iot=kwargs.get("consent_iot", False),
        consent_nlp=kwargs.get("consent_nlp", False),
        consent_sharing=kwargs.get("consent_sharing", False),
        sms_opt_out=kwargs.get("sms_opt_out", False),
        birth_year=kwargs.get("birth_year", 1985),
        sex=kwargs.get("sex", "M"),
        city_code=kwargs.get("city_code", "75000"),
    )
    db.add(patient)
    await db.flush()   # assign patient_uuid without committing
    return patient


# ── US-06: Consent Update ─────────────────────────────────

@pytest.mark.asyncio
async def test_consent_update_grants_flag(client, test_db):
    """Granting consent_iot must update the flag and return 200."""
    patient = await seed_patient(test_db, consent_iot=False)

    response = await client.patch(
        f"/api/v1/patients/{patient.patient_uuid}/consent",
        json={"consent_iot": True, "channel": "web"},
        headers=auth(doctor_token()),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["consent_iot"] is True
    assert data["consent_nlp"] is False    # unchanged
    assert data["consent_sharing"] is False


@pytest.mark.asyncio
async def test_consent_update_revokes_flag(client, test_db):
    """Revoking a previously granted consent must update and return 200."""
    patient = await seed_patient(test_db, consent_nlp=True)

    response = await client.patch(
        f"/api/v1/patients/{patient.patient_uuid}/consent",
        json={"consent_nlp": False, "channel": "app"},
        headers=auth(doctor_token()),
    )

    assert response.status_code == 200
    assert response.json()["consent_nlp"] is False


@pytest.mark.asyncio
async def test_consent_update_sms_opt_out(client, test_db):
    """Updating sms_opt_out must persist preference and return it in response."""
    patient = await seed_patient(test_db, sms_opt_out=False)

    response = await client.patch(
        f"/api/v1/patients/{patient.patient_uuid}/consent",
        json={"sms_opt_out": True, "channel": "app"},
        headers=auth(doctor_token()),
    )

    assert response.status_code == 200
    assert response.json()["sms_opt_out"] is True


@pytest.mark.asyncio
async def test_consent_no_change_is_idempotent(client, test_db):
    """Sending same value must return 200 without writing consent_log entry."""
    patient = await seed_patient(test_db, consent_iot=True)

    # Check baseline consent_log count
    from sqlalchemy import select, func
    count_before_result = await test_db.execute(
        select(func.count()).select_from(ConsentLog)
        .where(ConsentLog.patient_uuid == patient.patient_uuid)
    )
    count_before = count_before_result.scalar_one()

    response = await client.patch(
        f"/api/v1/patients/{patient.patient_uuid}/consent",
        json={"consent_iot": True, "channel": "web"},   # same value — no change
        headers=auth(doctor_token()),
    )

    assert response.status_code == 200

    # Flush session so subsequent queries see the current session state
    await test_db.flush()

    # No new consent_log entry must have been created
    count_after_result = await test_db.execute(
        select(func.count()).select_from(ConsentLog)
        .where(ConsentLog.patient_uuid == patient.patient_uuid)
    )
    count_after = count_after_result.scalar_one()
    assert count_after == count_before


@pytest.mark.asyncio
async def test_consent_writes_consent_log_entries(client, test_db):
    """Changing two flags must create two consent_log entries."""
    from sqlalchemy import select
    patient = await seed_patient(test_db, consent_iot=False, consent_nlp=False)

    await client.patch(
        f"/api/v1/patients/{patient.patient_uuid}/consent",
        json={"consent_iot": True, "consent_nlp": True, "channel": "web", "cgu_version": "1.0"},
        headers=auth(doctor_token()),
    )

    # Flush so the SELECT below can see data added by the endpoint in the same session
    await test_db.flush()

    logs_result = await test_db.execute(
        select(ConsentLog)
        .where(ConsentLog.patient_uuid == patient.patient_uuid)
        .order_by(ConsentLog.id)
    )
    logs = logs_result.scalars().all()
    assert len(logs) == 2
    assert {log.consent_type for log in logs} == {"iot", "nlp"}
    assert all(log.action == "granted" for log in logs)
    assert all(log.cgu_version == "1.0" for log in logs)


@pytest.mark.asyncio
async def test_consent_invalid_channel_returns_422(client, test_db):
    """An invalid channel value must be rejected with 422 Unprocessable Entity."""
    patient = await seed_patient(test_db)

    response = await client.patch(
        f"/api/v1/patients/{patient.patient_uuid}/consent",
        json={"consent_iot": True, "channel": "telegram"},   # not allowed
        headers=auth(doctor_token()),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_consent_patient_not_found_returns_404(client, test_db):
    """Non-existent patient_uuid must return 404."""
    response = await client.patch(
        f"/api/v1/patients/{uuid.uuid4()}/consent",
        json={"consent_iot": True, "channel": "web"},
        headers=auth(doctor_token()),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_consent_requires_auth(client, test_db):
    """Unauthenticated request must be rejected."""
    patient = await seed_patient(test_db)
    response = await client.patch(
        f"/api/v1/patients/{patient.patient_uuid}/consent",
        json={"consent_iot": True, "channel": "web"},
    )
    assert response.status_code == 403


# ── US-07: Data Export ────────────────────────────────────

@pytest.mark.asyncio
async def test_data_export_returns_patient_record(client, test_db):
    """Export must return the patient's pseudonymized record."""
    patient = await seed_patient(test_db, consent_iot=True, birth_year=1990, sex="F")

    response = await client.get(
        f"/api/v1/patients/{patient.patient_uuid}/data/export",
        headers=auth(admin_token()),
    )

    assert response.status_code == 200
    data = response.json()
    assert "exported_at" in data
    assert "patient" in data
    assert data["patient"]["patient_uuid"] == str(patient.patient_uuid)
    assert data["patient"]["consent_iot"] is True
    assert data["patient"]["birth_year"] == 1990
    assert "consent_history" in data
    assert "access_log" in data


@pytest.mark.asyncio
async def test_data_export_logs_audit_entry(client, test_db):
    """Every export must write an EXPORT entry to audit_logs."""
    from sqlalchemy import select
    patient = await seed_patient(test_db)

    await client.get(
        f"/api/v1/patients/{patient.patient_uuid}/data/export",
        headers=auth(admin_token()),
    )
    await test_db.flush()

    audit_result = await test_db.execute(
        select(AuditLog)
        .where(
            AuditLog.resource_uuid == patient.patient_uuid,
            AuditLog.action == "EXPORT",
        )
    )
    log = audit_result.scalar_one_or_none()
    assert log is not None
    assert log.actor_role == "admin"


@pytest.mark.asyncio
async def test_data_export_not_found_returns_404(client, test_db):
    """Non-existent patient UUID must return 404."""
    response = await client.get(
        f"/api/v1/patients/{uuid.uuid4()}/data/export",
        headers=auth(admin_token()),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_data_export_doctor_is_forbidden(client, test_db):
    """Doctor must not be able to export data — admin only."""
    patient = await seed_patient(test_db)

    response = await client.get(
        f"/api/v1/patients/{patient.patient_uuid}/data/export",
        headers=auth(doctor_token()),
    )
    assert response.status_code == 403


# ── US-08: Right to Erasure ───────────────────────────────

@pytest.mark.asyncio
async def test_erasure_anonymizes_patient_fields(client, test_db):
    """After erasure, ML fields must be None and is_active must be False."""
    from sqlalchemy import select
    patient = await seed_patient(test_db, birth_year=1975, sex="M", city_code="20000")

    response = await client.delete(
        f"/api/v1/patients/{patient.patient_uuid}",
        headers=auth(admin_token()),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["patient_uuid"] == str(patient.patient_uuid)
    assert "erased_at" in data

    # Flush so the endpoint's changes are visible to the next SELECT
    await test_db.flush()
    result = await test_db.execute(
        select(Patient).where(Patient.patient_uuid == patient.patient_uuid)
    )
    erased = result.scalar_one()
    assert erased.is_active is False
    assert erased.birth_year is None
    assert erased.sex is None
    assert erased.city_code is None
    assert erased.consent_iot is False
    assert erased.consent_nlp is False
    assert erased.consent_sharing is False
    assert erased.sms_opt_out is True


@pytest.mark.asyncio
async def test_erasure_logs_delete_audit_entry(client, test_db):
    """Erasure must write a DELETE entry to audit_logs."""
    from sqlalchemy import select
    patient = await seed_patient(test_db)

    await client.delete(
        f"/api/v1/patients/{patient.patient_uuid}",
        headers=auth(admin_token()),
    )
    await test_db.flush()

    audit_result = await test_db.execute(
        select(AuditLog)
        .where(
            AuditLog.resource_uuid == patient.patient_uuid,
            AuditLog.action == "DELETE",
        )
    )
    log = audit_result.scalar_one_or_none()
    assert log is not None
    assert log.actor_role == "admin"


@pytest.mark.asyncio
async def test_erasure_clears_conversation_cache(client, test_db):
    patient = await seed_patient(test_db)
    conv = Conversation(patient_id=patient.patient_uuid, language="fr")
    test_db.add(conv)
    await test_db.flush()

    with patch("app.api.v1.endpoints.patients.clear_patient_conversations", new=AsyncMock()) as mock_clear:
        response = await client.delete(
            f"/api/v1/patients/{patient.patient_uuid}",
            headers=auth(admin_token()),
        )

    assert response.status_code == 200
    mock_clear.assert_awaited_once_with(str(patient.patient_uuid), [str(conv.id)])


@pytest.mark.asyncio
async def test_erasure_already_erased_returns_409(client, test_db):
    """Re-erasing an already-erased patient must return 409 Conflict."""
    patient = await seed_patient(test_db)

    await client.delete(
        f"/api/v1/patients/{patient.patient_uuid}",
        headers=auth(admin_token()),
    )
    # Second call on same patient
    response = await client.delete(
        f"/api/v1/patients/{patient.patient_uuid}",
        headers=auth(admin_token()),
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_erasure_not_found_returns_404(client, test_db):
    """Non-existent patient UUID must return 404."""
    response = await client.delete(
        f"/api/v1/patients/{uuid.uuid4()}",
        headers=auth(admin_token()),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_erasure_doctor_is_forbidden(client, test_db):
    """Doctor must not be able to erase patients — admin only."""
    patient = await seed_patient(test_db)

    response = await client.delete(
        f"/api/v1/patients/{patient.patient_uuid}",
        headers=auth(doctor_token()),
    )
    assert response.status_code == 403
