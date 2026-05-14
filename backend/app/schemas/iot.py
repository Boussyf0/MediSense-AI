from datetime import datetime
from pydantic import BaseModel


class VitalPoint(BaseModel):
    ts: datetime
    hr: int
    spo2: int
    hrv: int

    model_config = {"from_attributes": True}


class DeviceStatus(BaseModel):
    paired: bool
    last_sync: datetime | None
    battery: int | None

    model_config = {"from_attributes": True}
