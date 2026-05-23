import asyncio
from app.db.session import engine, Base
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        # Create all tables in Base.metadata that don't exist yet
        await conn.run_sync(Base.metadata.create_all)
        print("Created tables successfully")

if __name__ == "__main__":
    asyncio.run(main())
