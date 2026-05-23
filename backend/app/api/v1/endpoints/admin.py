"""
Admin endpoints — Sprint 2 audit logs + Sprint 3 rerank evaluation.

Endpoints:
  GET /admin/audit-logs     US-46 — paginated, filterable audit trail
  POST /admin/rerank-eval   US-12 — compare RRF vs cross-encoder quality

ACCESS CONTROL:
  All endpoints in this module require admin role.

RGPD ART. 30:
  Organizations must maintain "records of processing activities".
  This endpoint is what the DPO (Data Protection Officer) uses to
  demonstrate RGPD compliance to regulators.
"""
from datetime import datetime
from typing import Annotated, Optional
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models.audit_log import AuditLog
from app.db.models.user import User, UserRole
from app.core.dependencies import require_admin, TokenPayload
from app.core.security import hash_password
from app.schemas.admin import AuditLogEntry, AuditLogList

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── US-46 — Audit Logs ────────────────────────────────────

@router.get(
    "/audit-logs",
    response_model=AuditLogList,
    summary="US-46 — Paginated audit trail (RGPD Art. 30)",
    description=(
        "Return the complete audit trail with optional filters. "
        "Used by the DPO to verify compliance and investigate incidents. "
        "Results are sorted newest-first. "
        "Max page size: 200 rows."
    ),
)
async def get_audit_logs(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_admin)],
    # ── Pagination ────────────────────────────────────────
    limit: int = Query(default=50, ge=1, le=200, description="Rows per page (max 200)"),
    offset: int = Query(default=0, ge=0, description="Starting row index"),
    # ── Filters ───────────────────────────────────────────
    actor_uuid: Optional[uuid.UUID] = Query(default=None, description="Filter by who performed the action"),
    resource_uuid: Optional[uuid.UUID] = Query(default=None, description="Filter by which patient/resource was accessed"),
    action: Optional[str] = Query(default=None, description="Filter by action type: READ, WRITE, DELETE, EXPORT, CONSENT, LOGIN"),
    actor_role: Optional[str] = Query(default=None, description="Filter by actor role: doctor, secretary, admin, patient"),
    from_date: Optional[datetime] = Query(default=None, description="Filter: events on or after this datetime (ISO 8601)"),
    to_date: Optional[datetime] = Query(default=None, description="Filter: events on or before this datetime (ISO 8601)"),
):
    """
    Paginated + filtered audit trail for RGPD Art. 30 compliance.

    This is the DPO's main tool for:
      - "Show me all accesses to patient X's data" → filter by resource_uuid
      - "Show me everything doctor Y did last week" → filter by actor_uuid + date range
      - "Show me all data exports" → filter by action=EXPORT
      - "Show me all erasures" → filter by action=DELETE

    HOW PAGINATION WORKS:
      offset=0, limit=50 → rows 1–50
      offset=50, limit=50 → rows 51–100
      offset=100, limit=50 → rows 101–150
      The 'total' field tells the frontend how many pages exist.

    WHY TWO QUERIES (count + data)?
      We need both the total count (for pagination UI) and the page data.
      SQLAlchemy can't do both in one query cleanly. Two queries is the
      standard approach and both are fast with the existing indexes.
    """
    # Build the base filter conditions
    conditions = []
    if actor_uuid:
        conditions.append(AuditLog.actor_uuid == actor_uuid)
    if resource_uuid:
        conditions.append(AuditLog.resource_uuid == resource_uuid)
    if action:
        conditions.append(AuditLog.action == action.upper())
    if actor_role:
        conditions.append(AuditLog.actor_role == actor_role.lower())
    if from_date:
        conditions.append(AuditLog.created_at >= from_date)
    if to_date:
        conditions.append(AuditLog.created_at <= to_date)

    # Query 1 — total count (for pagination metadata)
    count_query = select(func.count()).select_from(AuditLog)
    if conditions:
        count_query = count_query.where(*conditions)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Query 2 — paginated data, newest first
    data_query = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if conditions:
        data_query = data_query.where(*conditions)
    data_result = await db.execute(data_query)
    logs = data_result.scalars().all()

    return AuditLogList(
        total=total,
        limit=limit,
        offset=offset,
        items=[AuditLogEntry.model_validate(log) for log in logs],
    )


# ── US-12 — Cross-Encoder Re-ranking Evaluation ─────────

from pydantic import BaseModel, Field


class RerankEvalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Medical query in French")
    top_k: int = Field(default=20, ge=5, le=50, description="Number of chunks to retrieve and evaluate")


class RerankItem(BaseModel):
    rank: int
    doc: str
    score: float


class RerankEvalResponse(BaseModel):
    query: str
    rank_correlation: float
    top3_overlap: float
    mrr_rrf: float
    rrf_top3: list[str]
    ce_top3: list[str]
    num_chunks: int
    rrf_items: list[RerankItem]
    ce_items: list[RerankItem]
    ce_latency_ms: int


@router.post(
    "/rerank-eval",
    response_model=RerankEvalResponse,
    summary="US-12 — Compare RRF vs cross-encoder quality",
    description=(
        "Runs a query through both Qdrant RRF (hybrid search) and the "
        "mmarco multilingual cross-encoder, then compares the rankings. "
        "Used to validate that RRF quality is sufficient for the chat hot path."
    ),
)
async def evaluate_reranking(
    body: RerankEvalRequest,
    current_user: Annotated[TokenPayload, Depends(require_admin)],
):
    from app.rag.vectorstore import hybrid_search
    from app.rag.reranker import evaluate_rrf_vs_crossencoder, rerank

    chunks = hybrid_search(query_text=body.query, limit=body.top_k)

    if not chunks:
        return RerankEvalResponse(
            query=body.query,
            rank_correlation=0.0,
            top3_overlap=0.0,
            mrr_rrf=0.0,
            rrf_top3=[],
            ce_top3=[],
            num_chunks=0,
            rrf_items=[],
            ce_items=[],
            ce_latency_ms=0,
        )

    t0 = time.perf_counter()
    metrics = evaluate_rrf_vs_crossencoder(body.query, chunks)
    ce_latency_ms = int((time.perf_counter() - t0) * 1000)

    rrf_items = [
        RerankItem(
            rank=i + 1,
            doc=(c.get("text") or "")[:120],
            score=float(c.get("score", 0.0)),
        )
        for i, c in enumerate(chunks)
    ]

    ce_ranked = rerank(body.query, chunks, top_k=len(chunks))
    ce_items = [
        RerankItem(
            rank=i + 1,
            doc=(r.chunk.get("text") or "")[:120],
            score=float(r.ce_score),
        )
        for i, r in enumerate(ce_ranked)
    ]

    return RerankEvalResponse(
        query=body.query,
        num_chunks=len(chunks),
        rrf_items=rrf_items,
        ce_items=ce_items,
        ce_latency_ms=ce_latency_ms,
        **metrics,
    )


# ── US-12 (suite) — Multi-query batch eval ─────────────────

# Curated FR medical query set covering 4 categories. Each query is a realistic
# patient phrasing — designed to stress-test RRF on cases where BM25 may pull
# off-topic chunks (e.g. opioids matching "essoufflement" in their notice).
DEFAULT_QUERY_SUITE: list[str] = [
    # Cardio / urgences
    "douleurs thoraciques essoufflement insuffisance cardiaque",
    "palpitations arythmie fibrillation auriculaire",
    "hypertension arterielle traitement premiere intention",
    "AVC hemorragique symptomes reconnaissance precoce",
    "embolie pulmonaire signes cliniques",
    # Symptômes / triage
    "fievre persistante toux seche fatigue prolongee",
    "cephalee intense soudaine photophobie",
    "douleur abdominale aigue fosse iliaque droite",
    "diarrhee aigue deshydratation nourrisson",
    "vertiges nausees perte equilibre",
    # Médicaments / posologie
    "posologie paracetamol adulte fievre",
    "ibuprofene effets secondaires gastriques",
    "amoxicilline antibiotique angine streptocoque",
    "metformine diabete type 2 effets indesirables",
    "anticoagulant warfarine interactions alimentaires",
    # Maladies chroniques / suivi
    "diabete type 2 controle glycemie hba1c",
    "asthme crise traitement de fond",
    "depression majeure prise en charge",
    "insuffisance renale chronique creatinine",
    "BPCO bronchopneumopathie chronique obstructive",
]


class RerankSuiteRequest(BaseModel):
    queries: list[str] | None = Field(
        default=None,
        description="Custom query list. If null, the curated 20-query suite is used.",
    )
    top_k: int = Field(default=10, ge=5, le=20)


class RerankSuiteRow(BaseModel):
    query: str
    rank_correlation: float
    top3_overlap: float
    mrr_rrf: float
    ce_latency_ms: int
    num_chunks: int


class RerankSuiteAggregate(BaseModel):
    mean: float
    median: float
    std: float
    min: float
    max: float


class RerankSuiteResponse(BaseModel):
    n_queries: int
    n_evaluated: int  # queries that returned >= 1 chunk
    rank_correlation: RerankSuiteAggregate
    top3_overlap: RerankSuiteAggregate
    mrr_rrf: RerankSuiteAggregate
    ce_latency_ms: RerankSuiteAggregate
    rows: list[RerankSuiteRow]
    recommendation: str
    verdict: str  # "rrf_ok" | "ce_conditional" | "ce_required"


def _aggregate(values: list[float]) -> RerankSuiteAggregate:
    """Compute mean / median / std / min / max with one numpy call."""
    if not values:
        return RerankSuiteAggregate(mean=0, median=0, std=0, min=0, max=0)
    import numpy as np
    arr = np.array(values, dtype=float)
    return RerankSuiteAggregate(
        mean=float(arr.mean()),
        median=float(np.median(arr)),
        std=float(arr.std()),
        min=float(arr.min()),
        max=float(arr.max()),
    )


def _build_verdict(rho_mean: float, overlap_mean: float) -> tuple[str, str]:
    """Data-driven verdict — no hand-waving.

    Thresholds match the soutenance assessment grid:
      rho >= 0.5  AND overlap >= 0.66 → RRF alone is fine
      rho >= 0.2  OR  overlap >= 0.50 → CE conditional (urgent/critical queries)
      otherwise → CE in hot path is required
    """
    if rho_mean >= 0.5 and overlap_mean >= 0.66:
        return (
            "rrf_ok",
            f"RRF est suffisant en production. ρ moyen={rho_mean:.2f}, "
            f"overlap top-3={overlap_mean*3:.1f}/3. Économie de latence: ~50× "
            "vs cross-encoder.",
        )
    if rho_mean >= 0.2 or overlap_mean >= 0.50:
        return (
            "ce_conditional",
            f"RRF perd en qualité (ρ={rho_mean:.2f}, overlap top-3="
            f"{overlap_mean*3:.1f}/3). Recommandation: activer le cross-encoder "
            "uniquement sur les requêtes contenant des termes d'urgence "
            "ou de symptômes critiques (~30% du trafic).",
        )
    return (
        "ce_required",
        f"Qualité RRF insuffisante: ρ={rho_mean:.2f}, overlap top-3="
        f"{overlap_mean*3:.1f}/3. Le cross-encoder doit être placé dans le "
        "hot path — la perte de latence (~500ms) est acceptable au regard du "
        "risque clinique.",
    )


@router.post(
    "/rerank-eval/suite",
    response_model=RerankSuiteResponse,
    summary="US-12 — Batch RRF vs CE evaluation across N queries",
    description=(
        "Runs a curated (or custom) suite of medical queries through both "
        "Qdrant RRF and the cross-encoder. Returns aggregate quality metrics "
        "and a data-driven verdict on whether RRF alone is sufficient."
    ),
)
async def evaluate_reranking_suite(
    body: RerankSuiteRequest,
    current_user: Annotated[TokenPayload, Depends(require_admin)],
):
    from app.rag.vectorstore import hybrid_search
    from app.rag.reranker import evaluate_rrf_vs_crossencoder

    queries = body.queries or DEFAULT_QUERY_SUITE
    rows: list[RerankSuiteRow] = []

    for q in queries:
        chunks = hybrid_search(query_text=q, limit=body.top_k)
        if not chunks:
            continue
        t0 = time.perf_counter()
        metrics = evaluate_rrf_vs_crossencoder(q, chunks)
        ce_latency_ms = int((time.perf_counter() - t0) * 1000)
        rows.append(RerankSuiteRow(
            query=q,
            rank_correlation=metrics["rank_correlation"],
            top3_overlap=metrics["top3_overlap"],
            mrr_rrf=metrics["mrr_rrf"],
            ce_latency_ms=ce_latency_ms,
            num_chunks=len(chunks),
        ))

    rho_agg = _aggregate([r.rank_correlation for r in rows])
    overlap_agg = _aggregate([r.top3_overlap for r in rows])
    mrr_agg = _aggregate([r.mrr_rrf for r in rows])
    lat_agg = _aggregate([float(r.ce_latency_ms) for r in rows])

    verdict, recommendation = _build_verdict(rho_agg.mean, overlap_agg.mean)

    return RerankSuiteResponse(
        n_queries=len(queries),
        n_evaluated=len(rows),
        rank_correlation=rho_agg,
        top3_overlap=overlap_agg,
        mrr_rrf=mrr_agg,
        ce_latency_ms=lat_agg,
        rows=rows,
        recommendation=recommendation,
        verdict=verdict,
    )


# ── User Management ───────────────────────────────────────

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_uuid: uuid.UUID
    email: str
    role: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    total: int
    items: list[UserOut]


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


@router.get("/users", response_model=UserListResponse, summary="List all staff accounts")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_admin)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListResponse:
    total_result = await db.execute(select(func.count()).select_from(User))
    total = total_result.scalar_one()

    rows_result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    users = rows_result.scalars().all()

    return UserListResponse(total=total, items=[UserOut.model_validate(u) for u in users])


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new staff account",
)
async def create_user(
    body: UserCreateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_admin)],
) -> UserOut:
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email already registered: {body.email}",
        )

    if body.role == UserRole.PATIENT:
        from app.db.models.patient import Patient
        db.add(Patient(patient_uuid=user.user_uuid))
        await db.flush()

    await db.refresh(user)
    from app.core.audit import log_audit
    await log_audit(db, current_user, request, action="WRITE", resource_type="user",
                    resource_uuid=user.user_uuid)
    return UserOut.model_validate(user)


# ── Patient Management ────────────────────────────────────

class PatientCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    birth_year: int | None = Field(default=None, ge=1900, le=2025)
    sex: str | None = Field(default=None, pattern="^[MF]$")
    city_code: str | None = Field(default=None, max_length=10)
    chronic_conditions: list[str] = Field(default_factory=list)


class PatientOut(BaseModel):
    patient_uuid: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    birth_year: int | None
    sex: str | None
    city_code: str | None
    chronic_conditions: list[str]
    is_active: bool
    created_at: datetime


@router.post(
    "/patients",
    response_model=PatientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a patient account with ML demographics (User + Patient atomically)",
)
async def create_patient(
    body: PatientCreateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_admin)],
) -> PatientOut:
    """
    Create a patient account that works end-to-end:
      - User row (role=patient) → enables login
      - Patient row (same UUID) → enables appointment booking + ML prediction
      - PatientIdentity row (encrypted) → RGPD civil identity store

    The three rows share the same UUID so that JWT sub == patient_uuid
    throughout the entire application.
    """
    from sqlalchemy import text as sa_text
    from app.db.models.patient import Patient
    from app.core.config import get_settings
    from app.core.audit import log_audit

    # Pre-check to give a clean 409 before touching any rows
    dup = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email already registered: {body.email}",
        )

    shared_uuid = uuid.uuid4()
    settings = get_settings()

    user = User(
        user_uuid=shared_uuid,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=UserRole.PATIENT,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    patient = Patient(
        patient_uuid=shared_uuid,
        birth_year=body.birth_year,
        sex=body.sex,
        city_code=body.city_code,
        chronic_conditions=body.chronic_conditions if body.chronic_conditions else None,
    )
    db.add(user)
    db.add(patient)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email already registered: {body.email}",
        )

    # Encrypted civil identity (pgcrypto — same pattern as chat messages)
    full_name = f"{body.first_name or ''} {body.last_name or ''}".strip() or body.email
    await db.execute(
        sa_text("""
            INSERT INTO secure.patients_identity
                (patient_uuid, full_name_enc, email_enc, created_at)
            VALUES (
                :patient_uuid,
                pgp_sym_encrypt(:full_name, :key),
                pgp_sym_encrypt(:email, :key),
                NOW()
            )
        """),
        {
            "patient_uuid": str(shared_uuid),
            "full_name": full_name,
            "email": body.email,
            "key": settings.PGCRYPTO_KEY,
        },
    )

    await log_audit(db, current_user, request, action="WRITE", resource_type="patient",
                    resource_uuid=shared_uuid)

    return PatientOut(
        patient_uuid=shared_uuid,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        birth_year=body.birth_year,
        sex=body.sex,
        city_code=body.city_code,
        chronic_conditions=body.chronic_conditions,
        is_active=True,
        created_at=patient.created_at,
    )
