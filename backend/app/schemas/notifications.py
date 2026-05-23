from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeviceTokenRegister(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    platform: Literal["ios", "android", "web"]


class DeviceTokenResponse(BaseModel):
    id: str
    token: str
    platform: str
    created_at: str


class NotificationInboxItem(BaseModel):
    id: str
    appointment_uuid: str
    task_type: str
    status: str
    scheduled_for: datetime
    appointment_scheduled_at: datetime
    title: str
    body: str


class NotificationInboxResponse(BaseModel):
    items: list[NotificationInboxItem]
