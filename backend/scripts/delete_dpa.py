import asyncio
from sqlalchemy import text
from app.db.session import engine

async def main():
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.dpa_summaries WHERE patient_id = '5e479f4f-39f5-4fb7-8f35-1a7938477391'"))
        print("Deleted old DPA summaries")

if __name__ == "__main__":
    asyncio.run(main())
