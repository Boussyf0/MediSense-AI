import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from app.db.session import engine
from app.db.models.biometric_anomaly import BiometricAnomaly

async def main():
    patient_id = "5e479f4f-39f5-4fb7-8f35-1a7938477391"
    now = datetime.now(timezone.utc)
    
    async with engine.begin() as conn:
        # Check if an anomaly already exists
        result = await conn.execute(text(f"SELECT id FROM biometric_anomalies WHERE patient_id = '{patient_id}'"))
        if not result.fetchall():
            # Insert fake anomaly
            await conn.execute(text(f"""
                INSERT INTO biometric_anomalies (id, patient_id, metric_type, value, unit, threshold, severity, detected_at)
                VALUES ('{uuid.uuid4()}', '{patient_id}', 'hr', 115, 'bpm', 100, 'critical', '{now.isoformat()}')
            """))
            print("Inserted fake anomaly.")
        
        # Delete DPA summary
        await conn.execute(text(f"DELETE FROM dpa_summaries WHERE patient_id = '{patient_id}'"))
        print("Deleted cached DPA summary.")

if __name__ == "__main__":
    asyncio.run(main())
