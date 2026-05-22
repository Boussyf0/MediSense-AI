"""
Doctors directory endpoint — used by the Flutter booking screen to populate
the doctor dropdown. Read-only listing of active staff with role=doctor.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, Query
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
    specialty: str | None


@router.get("", response_model=List[DoctorItem])
async def list_doctors(
    specialty: str | None = Query(default=None, description="Filter by specialty"),
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(get_current_user),
):
    """List active doctors (any authenticated user can read this).

    Optional ?specialty= filter narrows the result for the booking flow.
    """
    query = select(User).where(
        User.role == UserRole.DOCTOR, User.is_active.is_(True)
    )
    if specialty:
        query = query.where(User.specialty == specialty)
    query = query.order_by(User.last_name.asc(), User.first_name.asc())
    rows = (await db.execute(query)).scalars().all()

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
                specialty=user.specialty,
            )
        )
    return items
