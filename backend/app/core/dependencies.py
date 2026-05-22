"""
FastAPI dependencies — injected into endpoints via Depends().

This pattern keeps auth logic OUT of endpoint code.
Every protected endpoint just adds:
    current_user: TokenPayload = Depends(get_current_user)
    # or for role-specific:
    _: TokenPayload = Depends(require_role("doctor"))
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from pydantic import BaseModel

from app.core.security import decode_token, is_token_blacklisted, check_permission

# HTTPBearer extracts the token from "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer()


class TokenPayload(BaseModel):
    """Structured representation of validated JWT claims."""
    sub: str        # user UUID
    role: str       # doctor | secretary | admin | patient
    jti: str        # token ID (for blacklist check)
    type: str       # access | refresh


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]
) -> TokenPayload:
    """
    Dependency that validates the JWT and returns the current user's claims.

    Checks performed:
      1. Token signature is valid (jose library)
      2. Token is not expired (jose library)
      3. Token type is 'access' (not a refresh token being misused)
      4. Token JTI is not in the Redis blacklist (not revoked)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        token_payload = TokenPayload(**payload)
    except (JWTError, KeyError, ValueError):
        raise credentials_exception

    # Reject refresh tokens used as access tokens
    if token_payload.type != "access":
        raise credentials_exception

    # Check Redis blacklist (handles logout/revocation)
    if await is_token_blacklisted(token_payload.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_payload


def require_role(*allowed_roles: str):
    """
    Factory that returns a dependency requiring specific roles.

    Usage:
        @router.get("/patients")
        async def get_patients(
            current_user: TokenPayload = Depends(require_role("doctor", "admin"))
        ):
            ...
    """
    async def role_checker(
        current_user: Annotated[TokenPayload, Depends(get_current_user)]
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(allowed_roles)}",
            )
        return current_user
    return role_checker


# Pre-built role dependencies for clean endpoint code
require_admin    = require_role("admin")
require_doctor   = require_role("doctor", "admin")
require_secretary = require_role("secretary", "admin")
require_patient  = require_role("patient")
require_caregiver = require_role("caregiver")
require_any_staff = require_role("doctor", "secretary", "admin")
