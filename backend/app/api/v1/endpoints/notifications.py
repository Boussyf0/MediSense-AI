"""Push-notification endpoints — Sprint 7 (US-29).

Mobile clients call POST /notifications/register-token after login to register
their FCM token, and DELETE /notifications/token/{token} on logout/uninstall.

GET /inbox is a polling fallback for clients without working FCM (iOS dev
without APNs entitlements, web clients, blocked-by-OS notifications).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.core.dependencies import TokenPayload, get_current_user
from app.db.models.appointment import Appointment
from app.db.models.device_token import DeviceToken
from app.db.models.notification import Notification
from app.db.models.sms_reminder_log import SmsReminderLog
from app.db.session import get_db
from app.schemas.notifications import (
    DeviceTokenRegister,
    DeviceTokenResponse,
    NotificationInboxItem,
    NotificationInboxResponse,
)
from app.services.sms_reminder import _build_sms_message

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post(
    "/register-token",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_token(
    payload: DeviceTokenRegister,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> DeviceTokenResponse:
    """Register or rebind an FCM token to the current user.

    A token is unique across the table; if it already exists for a different
    user (e.g. shared device), the prior row is removed before insert.
    """
    user_uuid = uuid.UUID(current_user.sub)

    # Detach token from any prior owner
    await db.execute(delete(DeviceToken).where(DeviceToken.token == payload.token))
    await db.flush()

    row = DeviceToken(
        user_uuid=user_uuid,
        token=payload.token,
        platform=payload.platform,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)

    return DeviceTokenResponse(
        id=str(row.id),
        token=row.token,
        platform=row.platform,
        created_at=row.created_at.isoformat(),
    )


@router.get("/inbox", response_model=NotificationInboxResponse)
async def list_inbox(
    since: datetime | None = Query(default=None, description="Return items strictly newer than this timestamp"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> NotificationInboxResponse:
    """List recent SMS reminders for the authenticated patient.

    Used by mobile clients without working FCM (iOS dev without APNs) as a
    poll-based fallback for push delivery.
    """
    patient_uuid = uuid.UUID(current_user.sub)
    q = (
        select(SmsReminderLog, Appointment)
        .join(Appointment, Appointment.appointment_uuid == SmsReminderLog.appointment_uuid)
        .where(
            Appointment.patient_uuid == patient_uuid,
            SmsReminderLog.status == "sent",
        )
    )
    if since is not None:
        q = q.where(SmsReminderLog.scheduled_for > since)
    q = q.order_by(SmsReminderLog.scheduled_for.desc()).limit(limit)
    rows = (await db.execute(q)).all()

    items = [
        NotificationInboxItem(
            id=str(log.id),
            appointment_uuid=str(log.appointment_uuid),
            task_type=log.task_type,
            status=log.status,
            scheduled_for=log.scheduled_for,
            appointment_scheduled_at=appt.scheduled_at,
            title="Rappel de rendez-vous",
            body=_build_sms_message(appt, float(appt.noshow_probability or 0.0)),
        )
        for log, appt in rows
    ]
    return NotificationInboxResponse(items=items)


@router.delete("/token/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_token(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    user_uuid = uuid.UUID(current_user.sub)
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.token == token, DeviceToken.user_uuid == user_uuid
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    await db.delete(row)
    await db.flush()


# ── General durable notification inbox (all roles) ───────────────────────────
# Backs the offline-account guarantee: appointment-lifecycle events are written
# to the `notification` table at event time, so the recipient sees them on next
# login regardless of FCM/connectivity. Works for patient, doctor and secretary.

class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    appointment_uuid: uuid.UUID | None = None
    read_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    unread_count: int


@router.get("", response_model=NotificationListResponse, summary="List my notifications")
async def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> NotificationListResponse:
    user_uuid = uuid.UUID(current_user.sub)
    q = select(Notification).where(Notification.user_uuid == user_uuid)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    items = (await db.execute(q)).scalars().all()

    unread_count = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_uuid == user_uuid,
                Notification.read_at.is_(None),
            )
        )
    ).scalar_one()

    return NotificationListResponse(
        items=[NotificationOut.model_validate(n) for n in items],
        unread_count=int(unread_count),
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    user_uuid = uuid.UUID(current_user.sub)
    notif = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_uuid == user_uuid,
            )
        )
    ).scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notif.read_at is None:
        from datetime import timezone
        notif.read_at = datetime.now(timezone.utc)
        await db.flush()
