"""
Tests for Sprint 2 admin endpoint.

US-46  GET /admin/audit-logs — paginated, filterable audit trail
"""
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models.audit_log import AuditLog


# ── Helpers ───────────────────────────────────────────────

def admin_token() -> str:
    return create_access_token(subject=str(uuid.uuid4()), role="admin")

def doctor_token() -> str:
    return create_access_token(subject=str(uuid.uuid4()), role="doctor")

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def seed_audit_log(
    db: AsyncSession,
    actor_uuid: uuid.UUID | None = None,
    actor_role: str = "doctor",
    action: str = "READ",
    resource_type: str = "patient",
    resource_uuid: uuid.UUID | None = None,
) -> AuditLog:
    """Insert an audit log entry into the test DB."""
    log = AuditLog(
        actor_uuid=actor_uuid or uuid.uuid4(),
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_uuid=resource_uuid,
    )
    db.add(log)
    await db.flush()
    return log


# ── US-46: Audit Logs ──────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_logs_returns_200(client, test_db):
    """Admin must get 200 with AuditLogList structure."""
    await seed_audit_log(test_db)
    await test_db.flush()

    response = await client.get(
        "/api/v1/admin/audit-logs",
        headers=auth(admin_token()),
    )

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_audit_logs_doctor_is_forbidden(client, test_db):
    """Doctor must not access audit logs — admin only."""
    response = await client.get(
        "/api/v1/admin/audit-logs",
        headers=auth(doctor_token()),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_requires_auth(client, test_db):
    """Unauthenticated request must be rejected."""
    response = await client.get("/api/v1/admin/audit-logs")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_pagination_limit(client, test_db):
    """Limit parameter must cap the number of items returned."""
    # Seed 5 logs
    for _ in range(5):
        await seed_audit_log(test_db)
    await test_db.flush()

    response = await client.get(
        "/api/v1/admin/audit-logs?limit=2&offset=0",
        headers=auth(admin_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["limit"] == 2
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_audit_logs_limit_max_200(client, test_db):
    """Limit above 200 must be rejected with 422."""
    response = await client.get(
        "/api/v1/admin/audit-logs?limit=999",
        headers=auth(admin_token()),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_audit_logs_filter_by_action(client, test_db):
    """Filter by action must return only matching entries."""
    patient_id = uuid.uuid4()
    await seed_audit_log(test_db, action="EXPORT", resource_uuid=patient_id)
    await seed_audit_log(test_db, action="READ", resource_uuid=patient_id)
    await test_db.flush()

    response = await client.get(
        f"/api/v1/admin/audit-logs?action=EXPORT&resource_uuid={patient_id}",
        headers=auth(admin_token()),
    )

    assert response.status_code == 200
    data = response.json()
    # All returned items must have action=EXPORT
    for item in data["items"]:
        assert item["action"] == "EXPORT"


@pytest.mark.asyncio
async def test_audit_logs_filter_by_resource_uuid(client, test_db):
    """Filter by resource_uuid must return only that patient's log entries."""
    target_patient = uuid.uuid4()
    other_patient = uuid.uuid4()

    await seed_audit_log(test_db, resource_uuid=target_patient)
    await seed_audit_log(test_db, resource_uuid=other_patient)
    await test_db.flush()

    response = await client.get(
        f"/api/v1/admin/audit-logs?resource_uuid={target_patient}",
        headers=auth(admin_token()),
    )

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["resource_uuid"] == str(target_patient)


@pytest.mark.asyncio
async def test_audit_logs_filter_by_actor_role(client, test_db):
    """Filter by actor_role must return only entries for that role."""
    await seed_audit_log(test_db, actor_role="admin", action="DELETE")
    await seed_audit_log(test_db, actor_role="doctor", action="READ")
    await test_db.flush()

    response = await client.get(
        "/api/v1/admin/audit-logs?actor_role=admin",
        headers=auth(admin_token()),
    )

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["actor_role"] == "admin"


@pytest.mark.asyncio
async def test_audit_logs_total_reflects_filters(client, test_db):
    """The 'total' field must match the filtered count, not the full table count."""
    export_patient = uuid.uuid4()
    # Seed 3 EXPORT logs for one patient, 2 READ logs for another
    for _ in range(3):
        await seed_audit_log(test_db, action="EXPORT", resource_uuid=export_patient)
    for _ in range(2):
        await seed_audit_log(test_db, action="READ")
    await test_db.flush()

    response = await client.get(
        f"/api/v1/admin/audit-logs?action=EXPORT&resource_uuid={export_patient}",
        headers=auth(admin_token()),
    )

    data = response.json()
    assert data["total"] == 3


# ── User Management ────────────────────────────────────────

USER_PAYLOAD = {
    "email": f"newdoc_{uuid.uuid4().hex[:8]}@clinique.ma",
    "password": "SecurePass123",
    "role": "doctor",
    "first_name": "Ahmed",
    "last_name": "Benali",
}


@pytest.mark.asyncio
async def test_create_user_returns_201(client):
    payload = {**USER_PAYLOAD, "email": f"doc_{uuid.uuid4().hex[:8]}@clinique.ma"}
    response = await client.post(
        "/api/v1/admin/users",
        json=payload,
        headers=auth(admin_token()),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["role"] == "doctor"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_create_user_requires_admin(client):
    response = await client.post(
        "/api/v1/admin/users",
        json={**USER_PAYLOAD, "email": f"doc_{uuid.uuid4().hex[:8]}@clinique.ma"},
        headers=auth(doctor_token()),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_user_duplicate_email_returns_409(client):
    email = f"dup_{uuid.uuid4().hex[:8]}@clinique.ma"
    payload = {**USER_PAYLOAD, "email": email}
    r1 = await client.post("/api/v1/admin/users", json=payload, headers=auth(admin_token()))
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/admin/users", json=payload, headers=auth(admin_token()))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_list_users_returns_200(client):
    email = f"list_{uuid.uuid4().hex[:8]}@clinique.ma"
    await client.post(
        "/api/v1/admin/users",
        json={**USER_PAYLOAD, "email": email},
        headers=auth(admin_token()),
    )
    response = await client.get("/api/v1/admin/users", headers=auth(admin_token()))
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert any(u["email"] == email for u in data["items"])


@pytest.mark.asyncio
async def test_list_users_requires_admin(client):
    response = await client.get("/api/v1/admin/users", headers=auth(doctor_token()))
    assert response.status_code == 403


# ── Rerank Eval ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_rerank_eval_happy(client, monkeypatch):
    fake_chunks = [
        {"id": "c1", "score": 0.91, "text": "Paracetamol soulage la douleur et la fievre chez l adulte"},
        {"id": "c2", "score": 0.84, "text": "Ibuprofene est un anti-inflammatoire non steroidien"},
        {"id": "c3", "score": 0.70, "text": "Aspirine est utilise contre la douleur et la fievre"},
    ]

    def fake_hybrid_search(query_text, limit):
        return fake_chunks

    def fake_eval(query, chunks):
        return {
            "rank_correlation": 0.91,
            "top3_overlap": 1.0,
            "mrr_rrf": 1.0,
            "rrf_top3": ["c1", "c2", "c3"],
            "ce_top3": ["c1", "c2", "c3"],
        }

    class FakeReranked:
        def __init__(self, chunk, ce_score):
            self.chunk = chunk
            self.ce_score = ce_score
            self.original_rank = 0

    def fake_rerank(query, chunks, top_k):
        return [FakeReranked(c, 0.99 - 0.1 * i) for i, c in enumerate(chunks)]

    monkeypatch.setattr("app.rag.vectorstore.hybrid_search", fake_hybrid_search)
    monkeypatch.setattr("app.rag.reranker.evaluate_rrf_vs_crossencoder", fake_eval)
    monkeypatch.setattr("app.rag.reranker.rerank", fake_rerank)

    response = await client.post(
        "/api/v1/admin/rerank-eval",
        json={"query": "paracetamol", "top_k": 5},
        headers=auth(admin_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "paracetamol"
    assert data["num_chunks"] == 3
    assert len(data["rrf_items"]) == 3
    assert len(data["ce_items"]) == 3
    assert data["rrf_items"][0]["rank"] == 1
    assert data["rrf_items"][0]["doc"].startswith("Paracetamol")
    assert "ce_latency_ms" in data
    assert isinstance(data["ce_latency_ms"], int)
    assert data["rank_correlation"] == 0.91


@pytest.mark.asyncio
async def test_rerank_eval_doctor_forbidden(client):
    response = await client.post(
        "/api/v1/admin/rerank-eval",
        json={"query": "paracetamol"},
        headers=auth(doctor_token()),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rerank_eval_empty_query_422(client):
    response = await client.post(
        "/api/v1/admin/rerank-eval",
        json={"query": ""},
        headers=auth(admin_token()),
    )
    assert response.status_code == 422
