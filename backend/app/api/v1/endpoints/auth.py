"""
Authentication endpoints — US-03 (JWT + refresh) + US-04 (RBAC).

Endpoints:
  POST /auth/login    → returns access_token + refresh_token
  POST /auth/refresh  → returns new access_token
  POST /auth/logout   → blacklists the current access_token in Redis
  GET  /auth/me       → returns current user info
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.db.session import get_db
from app.db.models.conversation import Conversation
from app.db.models.user import User
from app.core.conversation_cache import clear_patient_conversations
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    blacklist_token,
    is_token_blacklisted,
)
from app.core.audit import log_audit
from app.core.config import get_settings
from app.core.dependencies import get_current_user, TokenPayload
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, http_request: Request, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and return JWT tokens.

    Security notes:
      - Same error message for wrong email AND wrong password
        (prevents user enumeration attacks)
      - Timing: bcrypt.verify is slow by design — prevents brute force
    """
    # Look up user by email
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    # Intentionally vague error — don't reveal whether email exists
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Self-heal: every patient user must have a matching Patient row, otherwise
    # booking and IoT endpoints reject the JWT with "Patient not found". Legacy
    # accounts created before admin.py started inserting both rows are missing
    # this — insert it idempotently so existing accounts work end-to-end.
    if user.role.value == "patient":
        from app.db.models.patient import Patient
        existing = (
            await db.execute(
                select(Patient).where(Patient.patient_uuid == user.user_uuid)
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(Patient(patient_uuid=user.user_uuid))
            await db.flush()

    # Create token pair
    access_token = create_access_token(
        subject=str(user.user_uuid),
        role=user.role.value,
    )
    refresh_token, refresh_jti = create_refresh_token(
        subject=str(user.user_uuid),
        role=user.role.value,
    )

    # TODO Sprint 2: store refresh_jti in DB for rotation tracking
    # TODO Sprint 2: set refresh_token in httpOnly cookie (more secure than body)

    actor_payload = TokenPayload(sub=str(user.user_uuid), role=user.role.value, jti="", type="access")
    await log_audit(
        db=db,
        actor=actor_payload,
        request=http_request,
        action="LOGIN",
        resource_type="user",
        resource_uuid=user.user_uuid,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token.

    Why not just extend the access token's lifetime?
      - Short-lived access tokens limit damage if one is stolen
      - Refresh tokens can be revoked (stored in Redis blacklist)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        payload = decode_token(request.refresh_token)
    except JWTError:
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception

    jti = payload.get("jti")
    if not jti or await is_token_blacklisted(jti):
        raise credentials_exception

    # Issue new access token with same claims
    new_access_token = create_access_token(
        subject=payload["sub"],
        role=payload["role"],
    )

    return TokenResponse(
        access_token=new_access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke the current access token by adding its JTI to the Redis blacklist.

    The token remains cryptographically valid but will be rejected on next use.
    Redis TTL = token's remaining lifetime → no manual cleanup needed.
    """
    # Calculate remaining TTL for the access token
    remaining_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    await blacklist_token(current_user.jti, remaining_seconds)

    if current_user.role == "patient":
        patient_uuid = uuid.UUID(current_user.sub)
        stmt = select(Conversation.id).where(Conversation.patient_id == patient_uuid)
        result = await db.execute(stmt)
        conversation_ids = [str(row.id) for row in result.all()]
        await clear_patient_conversations(current_user.sub, conversation_ids)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's profile."""
    result = await db.execute(
        select(User).where(User.user_uuid == current_user.sub)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)
