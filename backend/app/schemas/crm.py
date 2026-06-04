"""
CRM task schemas — Sprint 6, US-43.

Used by GET /crm/tasks, PATCH /crm/tasks/{uuid}, POST /crm/tasks/{uuid}/retry.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

_VALID_SYNC_STATUSES = {"PENDING", "SENT", "FAILED", "SKIPPED", "CB_OPEN"}


class CRMTaskOut(BaseModel):
    """Single appointment CRM task — returned by GET and PATCH."""
    appointment_uuid: uuid.UUID
    patient_uuid: uuid.UUID
    patient_name: str | None = None
    salesforce_task_id: str | None
    crm_sync_status: str
    crm_correlation_id: str | None
    crm_retry_count: int
    crm_last_error: str | None
    crm_synced_at: datetime | None
    scheduled_at: datetime
    status: str
    urgency_flag: str | None

    model_config = {"from_attributes": True}


class CRMTaskPatch(BaseModel):
    """Request body for PATCH /crm/tasks/{uuid}."""
    salesforce_task_id: str | None = None
    crm_sync_status: str | None = None

    @field_validator("salesforce_task_id")
    @classmethod
    def validate_task_id_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 100:
            raise ValueError("salesforce_task_id max length is 100 characters")
        return v

    @field_validator("crm_sync_status")
    @classmethod
    def validate_sync_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_SYNC_STATUSES:
            raise ValueError(f"crm_sync_status must be one of {sorted(_VALID_SYNC_STATUSES)}")
        return v


class CRMRetryRequest(BaseModel):
    """Request body for POST /crm/tasks/{uuid}/retry."""
    force: bool = False


class CRMRetryResponse(BaseModel):
    """Response after dispatching a retry."""
    appointment_uuid: uuid.UUID
    crm_correlation_id: str | None
    crm_sync_status: str
    message: str


class CRMTaskListResponse(BaseModel):
    """Paginated list of CRM tasks."""
    total: int
    items: list[CRMTaskOut]
