"""
Audit helpers — write audit and consent log entries.

WHY A SEPARATE MODULE?
  Multiple endpoints (patients.py, admin.py, auth.py) all need to write
  audit entries. Centralising the logic here means:
    1. The log format is consistent across all endpoints
    2. Future changes (e.g. add a new field) happen in one place
    3. Endpoints stay focused on business logic, not logging boilerplate

USAGE PATTERN (in an endpoint):
    from fastapi import Request
    from app.core.audit import log_audit, log_consent

    @router.patch("/{patient_uuid}/consent")
    async def update_consent(
        patient_uuid: UUID,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: TokenPayload = Depends(require_doctor),
    ):
        # ... business logic ...
        await log_audit(
            db, current_user, request,
            action="CONSENT",
            resource_type="patient",
            resource_uuid=patient_uuid,
        )
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.db.models.audit_log import AuditLog, ConsentLog
from app.core.dependencies import TokenPayload


def _get_client_ip(request: Request) -> str | None:
    """
    Extract the real client IP from the request.

    Behind Nginx, the real IP is in X-Real-IP (set in nginx.conf).
    Fall back to request.client.host if the header is absent.
    """
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip
    return request.client.host if request.client else None


def _get_user_agent(request: Request) -> str | None:
    """Truncate user-agent to 255 chars to fit the DB column."""
    ua = request.headers.get("User-Agent")
    return ua[:255] if ua else None


async def log_audit(
    db: AsyncSession,
    actor: TokenPayload,
    request: Request,
    action: str,
    resource_type: str,
    resource_uuid: uuid.UUID | str | None = None,
) -> None:
    """
    Append one entry to public.audit_logs.

    Does NOT flush or commit — the entry will be written when the request's
    session commits at the end of get_db(). This keeps the audit write
    inside the same transaction as the main operation (atomicity: if the
    business operation rolls back, the audit entry rolls back too).

    Args:
        db            : the current async session (from Depends(get_db))
        actor         : the authenticated user making the request
        request       : the FastAPI Request object (for IP and user-agent)
        action        : e.g. 'READ', 'WRITE', 'DELETE', 'EXPORT', 'CONSENT'
        resource_type : e.g. 'patient', 'appointment'
        resource_uuid : UUID of the affected resource (optional)
    """
    if isinstance(resource_uuid, str):
        resource_uuid = uuid.UUID(resource_uuid)

    entry = AuditLog(
        actor_uuid=uuid.UUID(actor.sub),
        actor_role=actor.role,
        action=action,
        resource_type=resource_type,
        resource_uuid=resource_uuid,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )
    db.add(entry)


async def log_consent(
    db: AsyncSession,
    patient_uuid: uuid.UUID,
    consent_type: str,
    action: str,
    channel: str,
    request: Request,
    cgu_version: str | None = None,
) -> None:
    """
    Append one entry to public.consent_logs.

    Called once per consent flag that changes value. For example, if a patient
    grants IoT and revokes NLP in the same PATCH request, this function is
    called twice: once with ('iot', 'granted') and once with ('nlp', 'revoked').

    Args:
        db            : the current async session
        patient_uuid  : the patient whose consent changed
        consent_type  : 'iot' | 'nlp' | 'sharing'
        action        : 'granted' | 'revoked'
        channel       : 'app' | 'web' | 'paper'
        request       : for IP extraction
        cgu_version   : version of T&Cs the patient accepted (optional)
    """
    entry = ConsentLog(
        patient_uuid=patient_uuid,
        consent_type=consent_type,
        action=action,
        channel=channel,
        cgu_version=cgu_version,
        ip_address=_get_client_ip(request),
    )
    db.add(entry)
