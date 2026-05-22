from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class VitalPoint(BaseModel):
    ts: datetime
    hr: int
    spo2: int
    hrv: int | None

    model_config = {"from_attributes": True}


class DeviceStatus(BaseModel):
    paired: bool
    last_sync: datetime | None
    battery: int | None

    model_config = {"from_attributes": True}


class VitalSample(BaseModel):
    ts: datetime
    hr: int | None = Field(default=None, ge=20, le=250)
    spo2: int | None = Field(default=None, ge=50, le=100)
    hrv: int | None = Field(default=None, ge=0, le=300)


class IngestBatch(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    samples: list[VitalSample]
    battery: int | None = Field(default=None, ge=0, le=100)

    @field_validator("samples")
    @classmethod
    def _cap_batch_size(cls, v: list[VitalSample]) -> list[VitalSample]:
        if len(v) > 1000:
            raise ValueError("Batch too large: max 1000 samples per request.")
        return v


class IngestResponse(BaseModel):
    accepted: int
    dropped: int
