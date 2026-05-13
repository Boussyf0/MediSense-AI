import uuid
from datetime import datetime, time as TimeOfDay
from pydantic import BaseModel, Field, field_validator


def _validate_days(days: list[int]) -> list[int]:
    for d in days:
        if d < 0 or d > 6:
            raise ValueError("days_of_week values must be between 0 and 6")
    return days


class ReminderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    dosage: str = Field(..., min_length=1, max_length=80)
    time: TimeOfDay
    days_of_week: list[int] = Field(default_factory=list)

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, v: list[int]) -> list[int]:
        return _validate_days(v)


class ReminderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    dosage: str | None = Field(default=None, min_length=1, max_length=80)
    time: TimeOfDay | None = None
    days_of_week: list[int] | None = None
    enabled: bool | None = None

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        return _validate_days(v)


class ReminderOut(BaseModel):
    id: uuid.UUID
    name: str
    dosage: str
    time: TimeOfDay
    days_of_week: list[int]
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
