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
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func as sa_func, text, update, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.config import get_settings
from app.core.dependencies import TokenPayload, require_doctor
from app.db.session import get_db
from app.db.models.appointment import Appointment
from app.db.models.biometric_reading import BiometricReading
from app.db.models.conversation import Conversation
from app.db.models.dpa_summary import DPASummary, AgentAction
from app.db.models.patient import Patient
from app.db.models.user import User
from app.schemas.doctor import (
    DPAHistory,
    DPAPastAppointment,
    DPAPastSummary,
    DPAPatientCard,
    DPASummaryOut,
    IoTSummaryOut,
    IoTAnomalyOut,
    RecommendedAction,
    AgentActionOut,
    ApprovalRequest,
    RejectionRequest,
    DPAActionDecision,
    ApprovalResponse,
)
from app.schemas.doctor_brief import (
    AnomalyFlag,
    DoctorBriefResponse,
    NoShowRisk,
    PatientCard,
    SymptomMention,
    VitalsSnapshot,
)
from app.services import dpa_summarizer
from app.services.anomaly_detector import get_recent_scores
from app.services.noshow_predictor import (
    FeatureValidationError,
    ModelNotReadyError,
    build_appointment_features,
    get_risk_color,
    noshow_predictor,
)

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
    refresh: bool = Query(
        default=False,
        description="Force rebuild of a fresh PENDING summary instead of returning the latest existing one.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_doctor),
) -> DPASummaryOut:
    """
    Return the patient's most recent DPA summary so its approval state is
    visible to the doctor. Builds a fresh PENDING row only if none exists
    yet or the caller passes ?refresh=true (e.g. "Générer nouveau résumé").
    """
    await log_audit(
        db, current_user, request,
        action="READ",
        resource_type="dpa_summary",
        resource_uuid=patient_uuid,
    )

    summary: DPASummary | None = None
    if not refresh:
        latest = await db.execute(
            select(DPASummary)
            .where(DPASummary.patient_id == patient_uuid)
            .order_by(desc(DPASummary.created_at))
            .limit(1)
        )
        summary = latest.scalar_one_or_none()

    if summary is None:
        summary = await dpa_summarizer.build(
            patient_id=str(patient_uuid),
            db=db,
            doctor_id=current_user.sub,
        )

    payload = summary.payload_before
    freshness_minutes = int(
        (datetime.now(timezone.utc) - summary.created_at).total_seconds() / 60
    ) if summary.created_at else 0

    patient_name = None
    user_row = (
        await db.execute(
            select(User.first_name, User.last_name, User.email)
            .where(User.user_uuid == patient_uuid)
        )
    ).first()
    if user_row:
        first_name, last_name, email = user_row
        patient_name = " ".join(part for part in [first_name, last_name] if part) or email

    # Real demographic context — sourced from the Patient row (RGPD-minimal:
    # birth year → age, no DOB; sex; chronic conditions array).
    patient_card = DPAPatientCard()
    patient_row = (
        await db.execute(
            select(Patient.birth_year, Patient.sex, Patient.chronic_conditions)
            .where(Patient.patient_uuid == patient_uuid)
        )
    ).first()
    if patient_row:
        birth_year, sex, chronic = patient_row
        current_year = datetime.now(timezone.utc).year
        age = (current_year - birth_year) if birth_year else None
        patient_card = DPAPatientCard(
            age=age,
            sex=sex,
            chronic_conditions=list(chronic or []),
        )

    history = await _build_dpa_history(
        patient_uuid=patient_uuid,
        current_summary_id=summary.id,
        db=db,
    )

    return DPASummaryOut(
        summary_id=summary.id,
        patient_uuid=patient_uuid,
        patient_name=patient_name,
        patient=patient_card,
        symptoms=payload.get("symptoms", []),
        iot_summary=_parse_iot_summary(payload.get("iot_summary", {})),
        recommended_actions=_parse_actions(payload.get("recommended_actions", [])),
        agent_actions=_parse_agent_actions(getattr(summary, "actions", [])),
        confidence=payload.get("confidence", 0.0),
        data_freshness_minutes=freshness_minutes,
        status=summary.status,
        version=summary.version,
        created_at=summary.created_at,
        history=history,
    )


async def _build_dpa_history(
    *,
    patient_uuid: uuid.UUID,
    current_summary_id: uuid.UUID,
    db: AsyncSession,
) -> DPAHistory:
    """Aggregate clinical history that fills the empty-state UI when the
    current DPA windows (7d chat / 30d IoT) have no data."""
    now = datetime.now(timezone.utc)

    appt_rows = (await db.execute(
        select(
            Appointment.appointment_uuid,
            Appointment.scheduled_at,
            Appointment.status,
            Appointment.urgency_flag,
            Appointment.rag_summary,
        )
        .where(
            Appointment.patient_uuid == patient_uuid,
            Appointment.scheduled_at < now,
        )
        .order_by(desc(Appointment.scheduled_at))
        .limit(5)
    )).all()
    past_appointments = [
        DPAPastAppointment(
            appointment_uuid=row[0],
            scheduled_at=row[1],
            status=row[2],
            urgency_flag=row[3],
            rag_summary=row[4],
        )
        for row in appt_rows
    ]

    # Older summaries — exclude the one we're currently returning to avoid
    # the trivial "this summary appears in its own history" loop.
    summary_rows = (await db.execute(
        select(DPASummary)
        .where(
            DPASummary.patient_id == patient_uuid,
            DPASummary.id != current_summary_id,
        )
        .order_by(desc(DPASummary.created_at))
        .limit(3)
    )).scalars().all()
    previous_summaries: list[DPAPastSummary] = []
    for s in summary_rows:
        recs = (s.payload_before or {}).get("recommended_actions", [])
        top = None
        if isinstance(recs, list) and recs:
            first = recs[0] if isinstance(recs[0], dict) else {}
            kind = str(first.get("action", "")).strip()
            label = first.get("medication") or first.get("specialist") or first.get("metric") or first.get("message")
            top = f"{kind} — {label}" if kind and label else (kind or None)
        previous_summaries.append(DPAPastSummary(
            summary_id=s.id,
            created_at=s.created_at,
            status=s.status,
            actions_count=len(recs) if isinstance(recs, list) else 0,
            top_action=top,
        ))

    return DPAHistory(
        past_appointments=past_appointments,
        previous_summaries=previous_summaries,
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
    _assert_pending(summary)

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

    # Approve only actions still pending — preserves earlier per-action
    # rejections/modifications made via PATCH /action/{action_id}.
    if not body.edited_actions:
        await db.execute(
            update(AgentAction)
            .where(
                AgentAction.summary_id == summary_id,
                AgentAction.status == "pending",
            )
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
    _assert_pending(summary)

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
    # Refresh to ensure we read the actual DB state regardless of identity map cache.
    # SQLAlchemy's synchronize_session can leave stale values in the identity map
    # across requests sharing the same session (common in tests).
    await db.refresh(summary)
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


def _parse_agent_actions(raw: list) -> list[AgentActionOut]:
    """Convert ORM AgentAction rows to API-safe models."""
    out: list[AgentActionOut] = []
    if not isinstance(raw, list):
        return out
    for action in raw:
        try:
            out.append(
                AgentActionOut(
                    id=action.id,
                    action_type=action.action_type,
                    payload=action.payload or {},
                    modified_payload=action.modified_payload,
                    status=action.status,
                )
            )
        except Exception:
            continue
    return out


# ── 5-Minute Pre-Consult Brief ──────────────────────────────────────────────
#
# GET /doctor/agenda/{appointment_uuid}/brief
#
# Composes patient identity + 24h vitals + live anomaly narrative + last 3
# user symptom mentions + no-show risk in a single fanned-out query so the
# doctor's pre-visit panel loads in one round-trip.

@router.get(
    "/agenda/{appointment_uuid}/brief",
    response_model=DoctorBriefResponse,
    summary="5-minute pre-consult brief for a scheduled appointment",
)
async def get_appointment_brief(
    appointment_uuid: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_doctor),
) -> DoctorBriefResponse:
    await log_audit(
        db, current_user, request,
        action="READ",
        resource_type="appointment_brief",
        resource_uuid=appointment_uuid,
    )

    appt = (
        await db.execute(
            select(Appointment).where(Appointment.appointment_uuid == appointment_uuid)
        )
    ).scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")

    patient_uuid: uuid.UUID = appt.patient_uuid  # type: ignore[assignment]

    patient_card_task = _build_patient_card(db, patient_uuid)
    vitals_task = _build_vitals_snapshot(db, patient_uuid)
    anomaly_task = _build_anomaly_flag(patient_uuid)
    symptoms_task = _build_recent_symptoms(db, patient_uuid)
    noshow_task = _build_noshow_risk(db, appt)

    patient_card, vitals, anomaly, symptoms, noshow = await asyncio.gather(
        patient_card_task,
        vitals_task,
        anomaly_task,
        symptoms_task,
        noshow_task,
    )

    return DoctorBriefResponse(
        appointment_uuid=appointment_uuid,
        scheduled_at=appt.scheduled_at,  # type: ignore[arg-type]
        patient=patient_card,
        vitals=vitals,
        anomaly=anomaly,
        recent_symptoms=symptoms,
        noshow=noshow,
        generated_at=datetime.now(timezone.utc),
    )


async def _build_patient_card(db: AsyncSession, patient_uuid: uuid.UUID) -> PatientCard:
    """Patient demographics + a friendly display name from users table."""
    patient = (
        await db.execute(select(Patient).where(Patient.patient_uuid == patient_uuid))
    ).scalar_one_or_none()

    display_name: str | None = None
    user_row = (
        await db.execute(
            select(User.first_name, User.last_name, User.email)
            .where(User.user_uuid == patient_uuid)
        )
    ).first()
    if user_row:
        first_name, last_name, email = user_row
        display_name = " ".join(p for p in [first_name, last_name] if p) or email

    age: int | None = None
    sex: str | None = None
    chronic: list[str] = []
    if patient is not None:
        birth_year = patient.birth_year
        if birth_year:
            age = max(0, min(120, datetime.now(timezone.utc).year - int(birth_year)))
        sex = patient.sex  # type: ignore[assignment]
        chronic = list(patient.chronic_conditions or [])

    return PatientCard(
        patient_uuid=patient_uuid,
        display_name=display_name,
        age=age,
        sex=sex,
        chronic_conditions=chronic,
    )


async def _build_vitals_snapshot(db: AsyncSession, patient_uuid: uuid.UUID) -> VitalsSnapshot:
    """Last reading + count of samples in the trailing 24h window."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    last_reading = (
        await db.execute(
            select(BiometricReading)
            .where(
                BiometricReading.patient_uuid == patient_uuid,
                BiometricReading.ts >= since,
            )
            .order_by(desc(BiometricReading.ts))
            .limit(1)
        )
    ).scalar_one_or_none()

    samples_count = (
        await db.execute(
            select(sa_func.count(BiometricReading.id)).where(
                BiometricReading.patient_uuid == patient_uuid,
                BiometricReading.ts >= since,
            )
        )
    ).scalar_one() or 0

    if last_reading is None:
        return VitalsSnapshot(samples_24h=int(samples_count))

    return VitalsSnapshot(
        hr=last_reading.hr,            # type: ignore[arg-type]
        spo2=last_reading.spo2,        # type: ignore[arg-type]
        hrv=last_reading.hrv,          # type: ignore[arg-type]
        measured_at=last_reading.ts,   # type: ignore[arg-type]
        samples_24h=int(samples_count),
    )


async def _build_anomaly_flag(patient_uuid: uuid.UUID) -> AnomalyFlag:
    """Pull the live Redis-backed anomaly window scores + narrative."""
    try:
        scores = await get_recent_scores(str(patient_uuid))
    except Exception:  # pragma: no cover — Redis outage, degraded mode
        return AnomalyFlag()

    return AnomalyFlag(
        score_5m=scores.get("score_5m"),
        score_60m=scores.get("score_60m"),
        alert_critical=bool(scores.get("alert_critical")),
        trend_elevated=bool(scores.get("trend_elevated")),
        narrative=scores.get("narrative"),
    )


async def _build_recent_symptoms(
    db: AsyncSession, patient_uuid: uuid.UUID
) -> list[SymptomMention]:
    """Last 3 user-authored chat messages, decrypted via pgcrypto."""
    settings = get_settings()
    stmt = text("""
        SELECT pgp_sym_decrypt(m.content_encrypted, :key) AS content,
               m.created_at
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE c.patient_id = :patient_id
          AND m.role = 'user'
        ORDER BY m.created_at DESC
        LIMIT 3
    """)
    try:
        result = await db.execute(
            stmt, {"key": settings.PGCRYPTO_KEY, "patient_id": patient_uuid}
        )
        rows = result.all()
    except Exception:  # pragma: no cover — pgcrypto extension missing in some envs
        return []

    return [
        SymptomMention(content=row.content, created_at=row.created_at)
        for row in rows
        if row.content
    ]


async def _build_noshow_risk(db: AsyncSession, appt: Appointment) -> NoShowRisk:
    """Compute the no-show probability live; degrades gracefully if model is missing."""
    stored_prob = appt.noshow_probability
    stored_ver = appt.noshow_model_ver

    patient_uuid: uuid.UUID = appt.patient_uuid  # type: ignore[assignment]
    patient = (
        await db.execute(select(Patient).where(Patient.patient_uuid == patient_uuid))
    ).scalar_one_or_none()
    if patient is None:
        if stored_prob is not None:
            prob = float(stored_prob)  # type: ignore[arg-type]
            return NoShowRisk(
                probability=prob,
                risk_color=get_risk_color(prob),
                model_version=stored_ver,  # type: ignore[arg-type]
            )
        return NoShowRisk()

    previous_noshows = (
        await db.execute(
            select(sa_func.count(Appointment.appointment_uuid)).where(
                Appointment.patient_uuid == patient_uuid,
                Appointment.status == "NO_SHOW",
            )
        )
    ).scalar_one() or 0

    try:
        features = build_appointment_features(
            patient=patient,
            appointment=appt,
            previous_noshows=int(previous_noshows),
            now=datetime.now(timezone.utc),
        )
        prediction = noshow_predictor.predict(features)
        return NoShowRisk(
            probability=prediction["noshow_probability"],
            risk_color=prediction["risk_color"],
            model_version=prediction["model_version"],
        )
    except (ModelNotReadyError, FeatureValidationError):
        if stored_prob is not None:
            prob = float(stored_prob)  # type: ignore[arg-type]
            return NoShowRisk(
                probability=prob,
                risk_color=get_risk_color(prob),
                model_version=stored_ver,  # type: ignore[arg-type]
            )
        return NoShowRisk()
