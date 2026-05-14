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
    await db.refresh(user)
    from app.core.audit import log_audit
    await log_audit(db, current_user, request, action="WRITE", resource_type="user",
                    resource_uuid=user.user_uuid)
    return UserOut.model_validate(user)
