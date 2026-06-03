import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_patient, require_caregiver
from app.db.session import get_db
from app.db.models.user import User, UserRole
from app.db.models.caregiver import PatientCaregiver
from app.schemas.caregiver import CaregiverInvite, CaregiverPatientOut
from app.core.security import hash_password

router = APIRouter(tags=["caregiver"])

@router.post("/patient/caregiver/invite", summary="Patient invites a caregiver")
async def invite_caregiver(
    invite: CaregiverInvite,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
):
    """
    Patient invites a caregiver by email. 
    If the caregiver doesn't exist, an account is created with a default password.
    """
    patient_uuid = uuid.UUID(current_user.sub)

    # Find or create user
    user = (await db.execute(select(User).where(User.email == invite.email))).scalar_one_or_none()
    if not user:
        user = User(
            email=invite.email,
            first_name=invite.first_name,
            last_name=invite.last_name,
            role=UserRole.CAREGIVER,
            hashed_password=hash_password("Caregiver123!"), # In prod, send invite email
        )
        db.add(user)
        await db.flush()
    elif user.role != UserRole.CAREGIVER:
        raise HTTPException(status_code=400, detail="User already exists and is not a caregiver.")

    # Check if link exists
    link = (await db.execute(
        select(PatientCaregiver).where(
            PatientCaregiver.patient_uuid == patient_uuid,
            PatientCaregiver.caregiver_uuid == user.user_uuid
        )
    )).scalar_one_or_none()
    
    if link:
        if link.status == "rejected":
            link.status = "pending"
        else:
            return {"detail": "Invitation already sent or accepted."}
    else:
        link = PatientCaregiver(
            patient_uuid=patient_uuid,
            caregiver_uuid=user.user_uuid,
            status="pending"
        )
        db.add(link)

    await db.commit()
    return {"detail": "Caregiver invited.", "caregiver_uuid": str(user.user_uuid)}


@router.get("/caregiver/patients", response_model=list[CaregiverPatientOut], summary="Caregiver's patient list")
async def get_caregiver_patients(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_caregiver),
):
    caregiver_uuid = uuid.UUID(current_user.sub)

    # Get all patients linked to this caregiver
    links = (await db.execute(
        select(PatientCaregiver).where(PatientCaregiver.caregiver_uuid == caregiver_uuid)
    )).scalars().all()

    out = []
    for link in links:
        # In a real app, join with PatientIdentity to get names. 
        # For this demo, we'll just return UUID and status
        out.append(CaregiverPatientOut(
            patient_uuid=link.patient_uuid,
            status=link.status,
            invited_at=link.created_at
        ))
    return out


@router.post("/caregiver/invitations/{patient_uuid}/accept", summary="Caregiver accepts invitation")
async def accept_invitation(
    patient_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_caregiver),
):
    caregiver_uuid = uuid.UUID(current_user.sub)
    link = (await db.execute(
        select(PatientCaregiver).where(
            PatientCaregiver.patient_uuid == patient_uuid,
            PatientCaregiver.caregiver_uuid == caregiver_uuid,
            PatientCaregiver.status == "pending"
        )
    )).scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Pending invitation not found.")

    link.status = "accepted"
    await db.commit()
    return {"detail": "Invitation accepted."}


@router.get("/caregiver/dashboard/{patient_uuid}", summary="Filtered IoT dashboard for caregiver")
async def get_caregiver_dashboard(
    patient_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_caregiver),
):
    """
    Returns only the patient's vitals and alerts.
    Does NOT return NLP chat history or DPA summaries.
    """
    caregiver_uuid = uuid.UUID(current_user.sub)
    link = (await db.execute(
        select(PatientCaregiver).where(
            PatientCaregiver.patient_uuid == patient_uuid,
            PatientCaregiver.caregiver_uuid == caregiver_uuid,
            PatientCaregiver.status == "accepted"
        )
    )).scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=403, detail="Not authorized to view this patient.")

    # Re-use the vitals snapshot and anomaly flag from doctor endpoints
    from app.api.v1.endpoints.doctor import _build_vitals_snapshot, _build_anomaly_flag
    
    vitals = await _build_vitals_snapshot(db, patient_uuid)
    anomaly = await _build_anomaly_flag(patient_uuid)

    return {
        "patient_uuid": str(patient_uuid),
        "vitals": vitals.model_dump(),
        "anomaly": anomaly.model_dump(),
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }
