from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr

class CaregiverInvite(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

class CaregiverPatientOut(BaseModel):
    patient_uuid: UUID
    first_name: str | None = None
    last_name: str | None = None
    status: str
    invited_at: datetime
