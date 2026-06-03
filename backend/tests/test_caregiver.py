"""
Tests for caregiver endpoints — Sprint 8.

Coverage: POST /patient/caregiver/invite, GET /caregiver/patients,
POST /caregiver/invitations/{uuid}/accept, GET /caregiver/dashboard/{uuid}.

The caregiver endpoints call db.commit() instead of db.flush(), so we
monkeypatch commit → flush to preserve test isolation (rollback at teardown).
"""
import uuid
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token
from app.db.models.caregiver import PatientCaregiver
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole


def auth(role: str, sub: str | None = None) -> dict[str, str]:
    token = create_access_token(
        subject=sub or str(uuid.uuid4()), role=role
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_patient_user(test_db) -> tuple[uuid.UUID, str]:
    """Create a User(role=PATIENT) + Patient row. Returns (patient_uuid, token_sub)."""
    patient_uuid = uuid.uuid4()
    user = User(
        user_uuid=patient_uuid,
        email=f"patient-{patient_uuid}@test.ai",
        hashed_password="hashed",
        role=UserRole.PATIENT,
        first_name="Pat",
        last_name="Ient",
        is_active=True,
    )
    patient = Patient(
        patient_uuid=patient_uuid,
        consent_iot=False,
        consent_nlp=False,
        consent_sharing=False,
        sms_opt_out=False,
        birth_year=1990,
        sex="M",
        city_code="20000",
        chronic_conditions=[],
    )
    test_db.add(user)
    test_db.add(patient)
    await test_db.flush()
    return patient_uuid, str(patient_uuid)


async def _seed_caregiver_user(test_db) -> uuid.UUID:
    """Create a User(role=CAREGIVER). Returns caregiver UUID."""
    cg_uuid = uuid.uuid4()
    user = User(
        user_uuid=cg_uuid,
        email=f"caregiver-{cg_uuid}@test.ai",
        hashed_password="hashed",
        role=UserRole.CAREGIVER,
        first_name="Care",
        last_name="Giver",
        is_active=True,
    )
    test_db.add(user)
    await test_db.flush()
    return cg_uuid


def _patch_commit(test_db):
    """Monkeypatch db.commit → db.flush for test isolation."""
    return patch.object(test_db, "commit", test_db.flush)


# ── POST /patient/caregiver/invite ──────────────────────────────────────────


async def test_invite_caregiver_no_auth(client):
    """No bearer token → 403."""
    resp = await client.post(
        "/api/v1/patient/caregiver/invite",
        json={"email": "cg@test.ai", "first_name": "C", "last_name": "G"},
    )
    assert resp.status_code == 403


async def test_invite_caregiver_wrong_role(client):
    """Doctor role → 403 (patient-only endpoint)."""
    resp = await client.post(
        "/api/v1/patient/caregiver/invite",
        json={"email": "cg@test.ai", "first_name": "C", "last_name": "G"},
        headers=auth("doctor"),
    )
    assert resp.status_code == 403


async def test_invite_caregiver_new_user(client, test_db):
    """Patient invites a new email → user created + link created."""
    patient_uuid, sub = await _seed_patient_user(test_db)

    with _patch_commit(test_db):
        resp = await client.post(
            "/api/v1/patient/caregiver/invite",
            json={"email": "newcg@test.ai", "first_name": "New", "last_name": "CG"},
            headers=auth("patient", sub=sub),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "caregiver_uuid" in data
    assert data["detail"] == "Caregiver invited."


async def test_invite_caregiver_existing_user(client, test_db):
    """Patient invites an existing caregiver user → link created (no new user)."""
    patient_uuid, sub = await _seed_patient_user(test_db)
    cg_uuid = await _seed_caregiver_user(test_db)
    cg_email = f"caregiver-{cg_uuid}@test.ai"

    with _patch_commit(test_db):
        resp = await client.post(
            "/api/v1/patient/caregiver/invite",
            json={"email": cg_email, "first_name": "Care", "last_name": "Giver"},
            headers=auth("patient", sub=sub),
        )

    assert resp.status_code == 200
    assert resp.json()["caregiver_uuid"] == str(cg_uuid)


async def test_invite_caregiver_duplicate(client, test_db):
    """Second invite for same caregiver → returns 'already sent'."""
    patient_uuid, sub = await _seed_patient_user(test_db)
    cg_uuid = await _seed_caregiver_user(test_db)

    link = PatientCaregiver(
        patient_uuid=patient_uuid,
        caregiver_uuid=cg_uuid,
        status="pending",
    )
    test_db.add(link)
    await test_db.flush()

    cg_email = f"caregiver-{cg_uuid}@test.ai"
    with _patch_commit(test_db):
        resp = await client.post(
            "/api/v1/patient/caregiver/invite",
            json={"email": cg_email, "first_name": "Care", "last_name": "Giver"},
            headers=auth("patient", sub=sub),
        )

    assert resp.status_code == 200
    assert "already" in resp.json()["detail"].lower()


async def test_invite_non_caregiver_user_returns_400(client, test_db):
    """Inviting an email that belongs to a doctor → 400."""
    patient_uuid, sub = await _seed_patient_user(test_db)
    doc_uuid = uuid.uuid4()
    doc = User(
        user_uuid=doc_uuid,
        email="doc-existing@test.ai",
        hashed_password="hashed",
        role=UserRole.DOCTOR,
        first_name="Doc",
        last_name="Tor",
        is_active=True,
    )
    test_db.add(doc)
    await test_db.flush()

    with _patch_commit(test_db):
        resp = await client.post(
            "/api/v1/patient/caregiver/invite",
            json={"email": "doc-existing@test.ai", "first_name": "D", "last_name": "T"},
            headers=auth("patient", sub=sub),
        )

    assert resp.status_code == 400


# ── GET /caregiver/patients ─────────────────────────────────────────────────


async def test_get_caregiver_patients_no_auth(client):
    """No token → 403."""
    resp = await client.get("/api/v1/caregiver/patients")
    assert resp.status_code == 403


async def test_get_caregiver_patients(client, test_db):
    """Caregiver sees linked patients."""
    patient_uuid, _ = await _seed_patient_user(test_db)
    cg_uuid = await _seed_caregiver_user(test_db)

    link = PatientCaregiver(
        patient_uuid=patient_uuid,
        caregiver_uuid=cg_uuid,
        status="accepted",
    )
    test_db.add(link)
    await test_db.flush()

    resp = await client.get(
        "/api/v1/caregiver/patients",
        headers=auth("caregiver", sub=str(cg_uuid)),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["patient_uuid"] == str(patient_uuid)


# ── POST /caregiver/invitations/{uuid}/accept ───────────────────────────────


async def test_accept_invitation(client, test_db):
    """Accept a pending invitation → status changes to accepted."""
    patient_uuid, _ = await _seed_patient_user(test_db)
    cg_uuid = await _seed_caregiver_user(test_db)

    link = PatientCaregiver(
        patient_uuid=patient_uuid,
        caregiver_uuid=cg_uuid,
        status="pending",
    )
    test_db.add(link)
    await test_db.flush()

    with _patch_commit(test_db):
        resp = await client.post(
            f"/api/v1/caregiver/invitations/{patient_uuid}/accept",
            headers=auth("caregiver", sub=str(cg_uuid)),
        )

    assert resp.status_code == 200
    assert resp.json()["detail"] == "Invitation accepted."


async def test_accept_invitation_not_found(client, test_db):
    """Accept with no pending invitation → 404."""
    cg_uuid = await _seed_caregiver_user(test_db)

    resp = await client.post(
        f"/api/v1/caregiver/invitations/{uuid.uuid4()}/accept",
        headers=auth("caregiver", sub=str(cg_uuid)),
    )

    assert resp.status_code == 404


# ── GET /caregiver/dashboard/{uuid} ─────────────────────────────────────────


async def test_dashboard_no_accepted_link(client, test_db):
    """Dashboard without accepted link → 403."""
    cg_uuid = await _seed_caregiver_user(test_db)

    resp = await client.get(
        f"/api/v1/caregiver/dashboard/{uuid.uuid4()}",
        headers=auth("caregiver", sub=str(cg_uuid)),
    )

    assert resp.status_code == 403


async def test_dashboard_happy_path(client, test_db):
    """Dashboard with accepted link → 200 with vitals and anomaly data."""
    patient_uuid, _ = await _seed_patient_user(test_db)
    cg_uuid = await _seed_caregiver_user(test_db)

    link = PatientCaregiver(
        patient_uuid=patient_uuid,
        caregiver_uuid=cg_uuid,
        status="accepted",
    )
    test_db.add(link)
    await test_db.flush()

    # Mock the doctor helper functions that need Redis/IoT data.
    # These are imported lazily inside the endpoint, so patch at source.
    from unittest.mock import MagicMock

    vitals_obj = MagicMock()
    vitals_obj.model_dump.return_value = {"hr": 72, "spo2": 98}
    anomaly_obj = MagicMock()
    anomaly_obj.model_dump.return_value = {"has_anomaly": False}

    with patch("app.api.v1.endpoints.doctor._build_vitals_snapshot",
               AsyncMock(return_value=vitals_obj)), \
         patch("app.api.v1.endpoints.doctor._build_anomaly_flag",
               AsyncMock(return_value=anomaly_obj)):
        resp = await client.get(
            f"/api/v1/caregiver/dashboard/{patient_uuid}",
            headers=auth("caregiver", sub=str(cg_uuid)),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_uuid"] == str(patient_uuid)
    assert "vitals" in data
    assert "anomaly" in data
    assert "fetched_at" in data
