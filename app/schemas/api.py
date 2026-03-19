"""API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.audits import AuditResult
from app.schemas.candidates import MemoryCandidate


class EventIngestResponse(BaseModel):
    event_id: str
    dedupe_key: str
    status: str


class EventSummary(BaseModel):
    event_id: str
    conversation_id: str
    user_id: str
    status: str
    retry_count: int
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ApplySummary(BaseModel):
    apply_id: str
    final_action: str
    target_id: str | None = None
    mem0_memory_id: str | None = None
    apply_status: str
    graph_degraded: bool = False
    created_at: datetime


class EventDetailResponse(BaseModel):
    event: dict[str, Any]
    candidate: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    apply: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)


class EventListResponse(BaseModel):
    items: list[EventSummary]
    total: int


class DependencyStatus(BaseModel):
    name: str
    ok: bool
    detail: str


class ReadyResponse(BaseModel):
    ready: bool
    minimum_ready: bool
    dependencies: list[DependencyStatus]


class RetrievalResponse(BaseModel):
    injected_context: str
    memories: list[dict[str, Any]]
    graph_degraded: bool = False
