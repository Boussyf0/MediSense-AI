"""
Admin endpoints — Sprint 2 audit log access.

Endpoints:
  GET /admin/audit-logs   US-46 — paginated, filterable audit trail

ACCESS CONTROL:
  All endpoints in this module require admin role.
  Doctors and secretaries cannot access audit logs of other users.

RGPD ART. 30:
  Organizations must maintain "records of processing activities".
  This endpoint is what the DPO (Data Protection Officer) uses to
  demonstrate RGPD compliance to regulators.
"""
from datetime import datetime
from typing import Annotated, Optional
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models.audit_log import AuditLog
from app.core.dependencies import require_admin, TokenPayload
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
