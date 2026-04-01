"""
Security module — JWT creation/validation + password hashing + RBAC.

JWT Flow:
  1. User logs in → /auth/login returns access_token (15min) + refresh_token (7 days)
  2. Client stores refresh_token in httpOnly cookie (not localStorage — XSS protection)
  3. Client sends access_token in Authorization: Bearer header
  4. When access_token expires, client calls /auth/refresh → new access_token
  5. Logout: access_token JTI added to Redis blacklist until its TTL expires

Why JWT blacklist in Redis?
  - JWTs are stateless by design — you can't "invalidate" them without a blacklist
  - Redis TTL = token's remaining lifetime → entry auto-expires, no cleanup needed
  - Medical systems MUST support forced logout (e.g., device theft scenario)
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

# bcrypt with 12 rounds — strong enough for medical data, fast enough for UX
# rounds=12 ≈ 300ms per hash (acceptable for login, impractical for brute force)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """Hash a plain-text password. Never store or log the plain-text."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash (timing-safe comparison)."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Create a short-lived JWT access token.

    Claims:
      sub  — the user's UUID (subject)
      role — RBAC role (doctor | secretary | admin | patient)
      jti  — unique token ID (used for blacklisting on logout)
      exp  — expiration timestamp
      iat  — issued-at timestamp
      type — 'access' (distinguish from refresh tokens)
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(subject),
        "role": role,
        "jti": str(uuid.uuid4()),   # unique ID for blacklisting
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, role: str) -> tuple[str, str]:
    """
    Create a long-lived JWT refresh token.

    Returns (token, jti) — jti is stored server-side to enable revocation.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(subject),
        "role": role,
        "jti": jti,
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises JWTError if:
      - Signature is invalid (tampered token)
      - Token is expired
      - Required claims are missing
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── Redis Blacklist ───────────────────────────────────────

async def get_redis() -> aioredis.Redis:
    """Create async Redis connection."""
    return await aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


async def blacklist_token(jti: str, expires_in_seconds: int) -> None:
    """
    Add a token's JTI to the Redis blacklist.

    TTL = token's remaining lifetime → Redis auto-removes when token would
    have expired anyway, so the blacklist never grows unboundedly.
    """
    redis = await get_redis()
    await redis.setex(f"blacklist:{jti}", expires_in_seconds, "revoked")
    await redis.aclose()


async def is_token_blacklisted(jti: str) -> bool:
    """Check if a token has been revoked."""
    redis = await get_redis()
    result = await redis.get(f"blacklist:{jti}")
    await redis.aclose()
    return result is not None


# ── RBAC — Role-Based Access Control ─────────────────────

# Permission map: role → set of allowed endpoint prefixes
# This is the single source of truth for authorization
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "/api/v1/admin",
        "/api/v1/patients",
        "/api/v1/appointments",
        "/api/v1/users",
        "/api/v1/health",
    },
    "doctor": {
        "/api/v1/patients",
        "/api/v1/appointments",
        "/api/v1/dpa",
        "/api/v1/alerts",
        "/api/v1/health",
    },
    "secretary": {
        "/api/v1/appointments",
        "/api/v1/agenda",
        "/api/v1/health",
    },
    "patient": {
        "/api/v1/patient",    # patient's own data only
        "/api/v1/chat",
        "/api/v1/health",
    },
}


def check_permission(role: str, path: str) -> bool:
    """
    Check if a role has permission to access a given API path.

    Example:
        check_permission("secretary", "/api/v1/patients/uuid/dpa") → False
        check_permission("doctor", "/api/v1/patients/uuid/dpa")    → True
    """
    allowed_prefixes = ROLE_PERMISSIONS.get(role, set())
    return any(path.startswith(prefix) for prefix in allowed_prefixes)
