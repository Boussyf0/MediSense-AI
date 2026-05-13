"""
Doctors directory endpoint — used by the Flutter booking screen to populate
the doctor dropdown. Read-only listing of active staff with role=doctor.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, get_current_user
from app.db.models.user import User, UserRole
from app.db.session import get_db

router = APIRouter(prefix="/doctors", tags=["doctors"])


class DoctorItem(BaseModel):
    user_uuid: uuid.UUID
    first_name: str | None
    last_name: str | None
    email: str
    display_name: str


@router.get("", response_model=List[DoctorItem])
async def list_doctors(
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(get_current_user),
):
    """List active doctors (any authenticated user can read this)."""
    rows = (
        await db.execute(
            select(User)
            .where(User.role == UserRole.DOCTOR, User.is_active.is_(True))
            .order_by(User.last_name.asc(), User.first_name.asc())
        )
    ).scalars().all()

    items: List[DoctorItem] = []
    for user in rows:
        label = " ".join(
            part for part in [user.first_name, user.last_name] if part
        ) or user.email
        items.append(
            DoctorItem(
                user_uuid=user.user_uuid,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                display_name=f"Dr. {label}",
            )
        )
    return items
