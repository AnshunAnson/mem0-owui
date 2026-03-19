"""Audit schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app import constants
from app.schemas.candidates import MemoryCandidate


class AuditResult(BaseModel):
    decision: str
    final_action: str
    revised_candidate: MemoryCandidate | None = None
    audit_reason: str = ""
    audit_schema_version: str = constants.AUDIT_SCHEMA_VERSION


class AuditRecord(BaseModel):
    audit_id: str
    event_id: str
    candidate_id: str
    audit_result: AuditResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

