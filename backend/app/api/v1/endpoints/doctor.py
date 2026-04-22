"""
Doctor endpoints — US-41 (DPA summary) + US-42 (Human-in-the-Loop approval).

RBAC:
  All endpoints require 'doctor' or 'admin' role (Depends(require_doctor)).
  Every data access is audit-logged (RGPD Art. 30).

ENDPOINT MAP:
  GET  /doctor/patient/{uuid}/dpa-summary         → build + return DPA summary
  POST /doctor/dpa-summary/{id}/approve           → doctor approves AI recommendations
  POST /doctor/dpa-summary/{id}/reject            → doctor rejects with reason
  PATCH /doctor/dpa-summary/{id}/action/{act_id}  → approve/modify individual action

OPTIMISTIC LOCKING (US-42):
  The approve and reject endpoints compare the version field sent in the
  request against the DB version.  If they differ (another doctor acted first),
  HTTP 409 Conflict is returned with a clear message.

  Implementation:
    UPDATE dpa_summaries
    SET status=?, version=version+1, reviewed_at=now(), doctor_id=?
    WHERE id=? AND version=?
    → if rowcount == 0: someone else updated → 409

  We use SQLAlchemy's synchronize_session=False and check rowcount manually.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.dependencies import TokenPayload, require_doctor
from app.db.session import get_db
from app.db.models.dpa_summary import DPASummary, AgentAction
from app.schemas.doctor import (
    DPASummaryOut,
    IoTSummaryOut,
    IoTAnomalyOut,
    RecommendedAction,
    ApprovalRequest,
    RejectionRequest,
    DPAActionDecision,
    ApprovalResponse,
)
from app.services import dpa_summarizer

router = APIRouter(prefix="/doctor", tags=["doctor"])


# ── US-41: Build DPA Summary ─────────────────────────────────────────────────

@router.get(
    "/patient/{patient_uuid}/dpa-summary",
    response_model=DPASummaryOut,
    summary="Build AI-assisted DPA summary for a patient (doctor only)",
)
async def get_dpa_summary(
    patient_uuid: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_doctor),
) -> DPASummaryOut:
    """
    Build and return a DPA (Decision-support Panel) summary.

    Aggregates:
      - Patient symptoms from chat history (last 7 days)
      - Biometric anomalies from IoT sensors (last 30 days)
      - Rule-based recommended actions

    Creates a new dpa_summaries row in status=PENDING for doctor review.

    Performance target: < 500ms P95 (symptoms + IoT fetched in parallel).
    """
    await log_audit(
        db, current_user, request,
        action="READ",
        resource_type="dpa_summary",
        resource_uuid=patient_uuid,
    )

    # Build summary (aggregates 3 data sources, persists to DB)
    summary = await dpa_summarizer.build(
        patient_id=str(patient_uuid),
        db=db,
        doctor_id=current_user.sub,
    )

    payload = summary.payload_before
    freshness_minutes = int(
        (datetime.now(timezone.utc) - summary.created_at).total_seconds() / 60
    ) if summary.created_at else 0

    return DPASummaryOut(
        summary_id=summary.id,
        patient_uuid=patient_uuid,
        symptoms=payload.get("symptoms", []),
        iot_summary=_parse_iot_summary(payload.get("iot_summary", {})),
        recommended_actions=_parse_actions(payload.get("recommended_actions", [])),
        confidence=payload.get("confidence", 0.0),
        data_freshness_minutes=freshness_minutes,
        status=summary.status,
        version=summary.version,
        created_at=summary.created_at,
    )


# ── US-42: Approve ────────────────────────────────────────────────────────────

@router.post(
    "/dpa-summary/{summary_id}/approve",
    response_model=ApprovalResponse,
    summary="Doctor approves AI-generated DPA summary (with optional edits)",
)
async def approve_dpa_summary(
    summary_id: uuid.UUID,
    body: ApprovalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_doctor),
) -> ApprovalResponse:
    """
    Doctor approves the DPA summary.

    If body.edited_actions is provided → status becomes MODIFIED.
    Otherwise → status becomes APPROVED.

    Uses optimistic locking (version field) to prevent concurrent approvals.
    Returns HTTP 409 if another doctor approved first.
    """
    await log_audit(
        db, current_user, request,
        action="WRITE",
        resource_type="dpa_summary",
        resource_uuid=summary_id,
    )

    summary = await _get_or_404(summary_id, db)

    new_status = "MODIFIED" if body.edited_actions else "APPROVED"
    now = datetime.now(timezone.utc)
    doctor_uuid = uuid.UUID(current_user.sub)
    current_version = int(summary.version)  # freeze expected version before session sync

    # Build payload_after
    payload_after = dict(summary.payload_before)
    if body.edited_actions:
        payload_after["recommended_actions"] = [a.model_dump() for a in body.edited_actions]

    # Optimistic lock update
    stmt = (
        update(DPASummary)
        .where(
            DPASummary.id == summary_id,
            DPASummary.status == "PENDING",
            DPASummary.version == current_version,
        )
        .values(
            status=new_status,
            version=current_version + 1,
            doctor_id=doctor_uuid,
            payload_after=payload_after,
            doctor_note=body.doctor_note,
            reviewed_at=now,
        )
    )
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce résumé a déjà été traité par un autre médecin. Veuillez actualiser.",
        )

    # Approve all individual actions (unless doctor provided specific edits)
    if not body.edited_actions:
        await db.execute(
            update(AgentAction)
            .where(AgentAction.summary_id == summary_id)
            .values(status="approved", decided_at=now, decided_by=doctor_uuid)
        )

    return ApprovalResponse(
        summary_id=summary_id,
        status=new_status,
        version=current_version + 1,
        reviewed_at=now,
        message=f"Résumé {new_status.lower()} avec succès.",
    )


# ── US-42: Reject ─────────────────────────────────────────────────────────────

@router.post(
    "/dpa-summary/{summary_id}/reject",
    response_model=ApprovalResponse,
    summary="Doctor rejects AI-generated DPA summary with mandatory reason",
)
async def reject_dpa_summary(
    summary_id: uuid.UUID,
    body: RejectionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_doctor),
) -> ApprovalResponse:
    """
    Doctor rejects the DPA summary.

    A reason is mandatory (min 10 chars) — logged for model retraining.
    Uses optimistic locking — returns HTTP 409 if already processed.
    """
    await log_audit(
        db, current_user, request,
        action="WRITE",
        resource_type="dpa_summary",
        resource_uuid=summary_id,
    )

    summary = await _get_or_404(summary_id, db)

    now = datetime.now(timezone.utc)
    doctor_uuid = uuid.UUID(current_user.sub)
    current_version = int(summary.version)  # freeze expected version before session sync

    stmt = (
        update(DPASummary)
        .where(
            DPASummary.id == summary_id,
            DPASummary.status == "PENDING",
            DPASummary.version == current_version,
        )
        .values(
            status="REJECTED",
            version=current_version + 1,
            doctor_id=doctor_uuid,
            doctor_note=body.doctor_note,
            reviewed_at=now,
        )
    )
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce résumé a déjà été traité par un autre médecin. Veuillez actualiser.",
        )

    # Reject all individual actions
    await db.execute(
        update(AgentAction)
        .where(AgentAction.summary_id == summary_id)
        .values(status="rejected", decided_at=now, decided_by=doctor_uuid)
    )

    return ApprovalResponse(
        summary_id=summary_id,
        status="REJECTED",
        version=current_version + 1,
        reviewed_at=now,
        message="Résumé rejeté. Raison enregistrée pour amélioration du modèle.",
    )


# ── US-42: Per-action decision ────────────────────────────────────────────────

@router.patch(
    "/dpa-summary/{summary_id}/action/{action_id}",
    response_model=ApprovalResponse,
    summary="Doctor approves, rejects, or modifies a single recommended action",
)
async def decide_action(
    summary_id: uuid.UUID,
    action_id: uuid.UUID,
    body: DPAActionDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_doctor),
) -> ApprovalResponse:
    """
    Doctor decides on a single action within a DPA summary.

    This allows granular control: approve prescription, reject referral, etc.
    The parent summary status stays PENDING until the doctor explicitly calls
    /approve or /reject on the whole summary.
    """
    await log_audit(
        db, current_user, request,
        action="WRITE",
        resource_type="agent_action",
        resource_uuid=action_id,
    )

    # Verify action belongs to this summary
    stmt = select(AgentAction).where(
        AgentAction.id == action_id,
        AgentAction.summary_id == summary_id,
    )
    result = await db.execute(stmt)
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Action introuvable")

    now = datetime.now(timezone.utc)
    doctor_uuid = uuid.UUID(current_user.sub)

    await db.execute(
        update(AgentAction)
        .where(AgentAction.id == action_id)
        .values(
            status=body.status,
            modified_payload=body.modified_payload,
            decided_at=now,
            decided_by=doctor_uuid,
        )
    )

    # Retrieve parent summary version for response
    summary = await _get_or_404(summary_id, db)
    return ApprovalResponse(
        summary_id=summary_id,
        status=summary.status,
        version=summary.version,
        reviewed_at=now,
        message=f"Action {body.status}.",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(summary_id: uuid.UUID, db: AsyncSession) -> DPASummary:
    result = await db.execute(
        select(DPASummary).where(DPASummary.id == summary_id)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Résumé DPA introuvable")
    return summary


def _assert_pending(summary: DPASummary) -> None:
    status_val: str = summary.status  # type: ignore[assignment]
    if status_val != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ce résumé est déjà en statut {status_val}. Impossible de modifier.",
        )


def _parse_iot_summary(raw: dict) -> IoTSummaryOut:
    """Convert raw JSONB iot_summary dict to IoTSummaryOut schema."""
    anomalies = [
        IoTAnomalyOut(**a) for a in raw.get("latest_anomalies", [])
        if isinstance(a, dict)
    ]
    return IoTSummaryOut(
        latest_anomalies=anomalies,
        trend=raw.get("trend", "stable"),
    )


def _parse_actions(raw: list) -> list[RecommendedAction]:
    """Convert raw JSONB recommended_actions list to RecommendedAction schemas."""
    actions = []
    for a in raw:
        if isinstance(a, dict):
            try:
                actions.append(RecommendedAction(**a))
            except Exception:
                pass
    return actions
