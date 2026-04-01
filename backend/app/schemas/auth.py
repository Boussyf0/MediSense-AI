"""
Authentication schemas — Pydantic models for request/response validation.

Why separate schemas from ORM models?
  - The DB model (User) has hashed_password — you never want that in an API response
  - Pydantic validates and sanitizes input BEFORE it touches the DB
  - Different endpoints need different views of the same data
"""
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator
import re


class LoginRequest(BaseModel):
    """OAuth2 password grant — used by /auth/login."""
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v or len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class TokenResponse(BaseModel):
    """Response from /auth/login and /auth/refresh."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int     # seconds until access_token expires


class RefreshRequest(BaseModel):
    """Request body for /auth/refresh."""
    refresh_token: str


class UserResponse(BaseModel):
    """Public representation of a user — no password field."""
    user_uuid: UUID  # UUID object from ORM, serializes to string in JSON
    email: str
    role: str
    first_name: str | None
    last_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}   # allows ORM model → Pydantic conversion
