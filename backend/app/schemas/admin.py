"""
Admin schemas — Pydantic models for admin-only endpoints (Sprint 2+).

Schemas defined here:
  AuditLogEntry  — single row from public.audit_logs
  AuditLogList   — paginated response for GET /admin/audit-logs (US-46)
"""
from datetime import datetime
from uuid import UUID
from typing import Any, Optional, List
from pydantic import BaseModel, field_validator


class AuditLogEntry(BaseModel):
    """
    Full representation of a single audit log row.

    Only admin users can see the full log (actor_uuid, ip_address).
    The patient data export (PatientDataExport) uses a reduced version
    (AuditLogExportEntry) that hides identifying fields.
    """
    id: int
    actor_uuid: UUID
    actor_role: str
    action: str
    resource_type: str
    resource_uuid: Optional[UUID]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("ip_address", mode="before")
    @classmethod
    def coerce_ip(cls, v: Any) -> Optional[str]:
        return str(v) if v is not None else None


class AuditLogList(BaseModel):
    """
    Paginated response for GET /admin/audit-logs (US-46).

    Pagination fields:
      total   — total matching rows (for the frontend to calculate pages)
      limit   — page size used for this request
      offset  — starting offset used for this request
      items   — the rows for this page
    """
    total: int
    limit: int
    offset: int
    items: List[AuditLogEntry]
