"""
CRM endpoints — Sprint 6, US-43.

Secretary-facing API to manage Salesforce task synchronisation.
All three endpoints require secretary or admin role (RBAC).

Design constraints:
  - CRM retries are fire-and-forget (asyncio.create_task) — response
    returns immediately; Salesforce call happens in background.
  - All writes use await db.flush() — never commit inside endpoint.
  - All data access is recorded in audit_logs (RGPD Art. 30).
"""
import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.config import get_settings
from app.core.dependencies import TokenPayload, require_secretary
from app.db.models.appointment import Appointment
from app.db.session import AsyncSessionLocal, get_db
from app.services.salesforce_client import send_crm_event
from app.schemas.crm import (
    CRMRetryRequest,
    CRMRetryResponse,
    CRMTaskListResponse,
    CRMTaskOut,
    CRMTaskPatch,
)

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/tasks", response_model=CRMTaskListResponse)
async def list_crm_tasks(
    request: Request,
    crm_sync_status: str | None = Query(default=None, description="Filter by sync status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_secretary),
) -> CRMTaskListResponse:
    """List appointments with CRM sync status. Secretary/admin only."""
    base_q = select(Appointment)
    if crm_sync_status is not None:
        base_q = base_q.where(Appointment.crm_sync_status == crm_sync_status)

    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar_one()

    rows_result = await db.execute(
        base_q.order_by(Appointment.scheduled_at.desc()).limit(limit).offset(offset)
    )
    rows = rows_result.scalars().all()

    await log_audit(db, current_user, request, action="READ", resource_type="crm_task")
    return CRMTaskListResponse(total=total, items=[CRMTaskOut.model_validate(r) for r in rows])


@router.patch("/tasks/{appointment_uuid}", response_model=CRMTaskOut)
async def update_crm_task(
    appointment_uuid: uuid.UUID,
    body: CRMTaskPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_secretary),
) -> CRMTaskOut:
    """Update salesforce_task_id or crm_sync_status. Secretary/admin only."""
    result = await db.execute(
        select(Appointment).where(Appointment.appointment_uuid == appointment_uuid)
    )
    appt = result.scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if body.salesforce_task_id is not None:
        appt.salesforce_task_id = body.salesforce_task_id
    if body.crm_sync_status is not None:
        appt.crm_sync_status = body.crm_sync_status

    await db.flush()
    await log_audit(db, current_user, request, action="WRITE",
                    resource_type="crm_task", resource_uuid=appointment_uuid)
    return CRMTaskOut.model_validate(appt)


@router.post("/tasks/{appointment_uuid}/retry", response_model=CRMRetryResponse)
async def retry_crm_task(
    appointment_uuid: uuid.UUID,
    body: CRMRetryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_secretary),
) -> CRMRetryResponse:
    """Dispatch a non-blocking Salesforce retry for a failed task. Secretary/admin only."""
    result = await db.execute(
        select(Appointment).where(Appointment.appointment_uuid == appointment_uuid)
    )
    appt = result.scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if appt.crm_sync_status == "SENT" and not body.force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task already sent. Use force=true to retry anyway.",
        )

    settings = get_settings()
    if appt.crm_retry_count >= settings.SALESFORCE_MAX_RETRIES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Max retries ({settings.SALESFORCE_MAX_RETRIES}) reached for this task.",
        )

    # Fire-and-forget with a dedicated session so DB persist works after the
    # request session closes.  The background coroutine owns its own transaction.
    _appt_id = str(appt.appointment_uuid)
    _patient_id = str(appt.patient_uuid)
    _urgency = appt.urgency_flag

    async def _do_retry() -> None:
        async with AsyncSessionLocal() as bg_db:
            try:
                await send_crm_event(
                    patient_id=_patient_id,
                    severity="routine",
                    appointment_id=_appt_id,
                    specialist_type=_urgency,
                    query_fr="[secretary-initiated retry]",
                    iot_triggered=False,
                    db=bg_db,
                )
                await bg_db.commit()
            except Exception:
                await bg_db.rollback()

    asyncio.create_task(_do_retry())

    appt.crm_sync_status = "PENDING"
    await db.flush()

    await log_audit(db, current_user, request, action="WRITE",
                    resource_type="crm_task", resource_uuid=appointment_uuid)

    return CRMRetryResponse(
        appointment_uuid=appointment_uuid,
        crm_correlation_id=appt.crm_correlation_id,
        crm_sync_status="PENDING",
        message="Retry dispatched asynchronously.",
    )
