import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.db.models.biometric_reading import BiometricReading
from app.db.models.conversation import Conversation, Message
from app.db.models.patient import Patient, PatientIdentity

AHMED_UUID_STR = "5e479f4f-39f5-4fb7-8f35-1a7938477391"

async def main() -> None:
    patient_uuid = uuid.UUID(AHMED_UUID_STR)
    
    async with AsyncSessionLocal() as db:
        # Check if patient exists
        patient = (await db.execute(select(Patient).where(Patient.patient_uuid == patient_uuid))).scalar_one_or_none()
        if not patient:
            print("Patient Ahmed Benali not found. Seed the DB first.")
            return
            
        print("Seeding biometric data for the last 24h...")
        now = datetime.now(timezone.utc)
        
        # Insert some vitals
        for i in range(10):
            ts = now - timedelta(hours=23 - i*2)
            reading = BiometricReading(
                patient_uuid=patient_uuid,
                ts=ts,
                hr=85 + i,
                spo2=96 - (i%2),
                hrv=40 + (i*2),
            )
            db.add(reading)
            
        # Add a critical alert reading right now
        db.add(BiometricReading(
            patient_uuid=patient_uuid,
            ts=now,
            hr=115,
            spo2=88,
            hrv=25,
        ))
        
        print("Seeding conversation / symptoms...")
        # Check if conversation exists
        conv = (await db.execute(select(Conversation).where(Conversation.patient_id == patient_uuid).limit(1))).scalar_one_or_none()
        if not conv:
            conv = Conversation(patient_id=patient_uuid)
            db.add(conv)
            await db.commit()
            
        # Add some messages (symptoms)
        from app.core.config import get_settings
        settings = get_settings()
        
        # We need to insert encrypted messages using raw SQL since the model uses pgcrypto
        stmt = text("""
            INSERT INTO messages (conversation_id, role, content_encrypted, created_at)
            VALUES (:conv_id, 'user', pgp_sym_encrypt(:content, :key), :created_at)
        """)
        
        symptoms = [
            "Je me sens très fatigué depuis hier.",
            "J'ai des essoufflements même au repos.",
            "Ma poitrine me serre un peu."
        ]
        
        for i, sym in enumerate(symptoms):
            await db.execute(stmt, {
                "conv_id": conv.id,
                "content": sym,
                "key": settings.PGCRYPTO_KEY,
                "created_at": now - timedelta(days=2 - i)
            })
            
        await db.commit()
        print("Seed complete! Refresh the Doctor Brief and DPA Summary.")

if __name__ == "__main__":
    asyncio.run(main())
