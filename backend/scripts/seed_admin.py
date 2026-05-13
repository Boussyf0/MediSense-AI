"""
One-shot script to create the initial admin user.

Usage (from repo root):
  docker exec -w /app medisense_fastapi python scripts/seed_admin.py
  # or locally:
  cd backend && python scripts/seed_admin.py

Credentials: admin@medisense.ma / Admin1234!
Change the password immediately after first login.
"""
import asyncio
import os

EMAIL = os.getenv("ADMIN_EMAIL", "admin@medisense.ma")
PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234!")


async def main() -> None:
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.user import User, UserRole
    from app.core.security import hash_password

    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == EMAIL))
        ).scalar_one_or_none()
        if existing:
            print(f"Admin already exists: {EMAIL}")
            return
        user = User(
            email=EMAIL,
            hashed_password=hash_password(PASSWORD),
            role=UserRole.ADMIN,
            first_name="Admin",
            last_name="MediSense",
        )
        db.add(user)
        await db.commit()
        print(f"Created admin: {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
