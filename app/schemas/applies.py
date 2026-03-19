"""Apply schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ApplyResult(BaseModel):
    apply_id: str
    final_action: str
    target_id: str | None = None
    mem0_memory_id: str | None = None
    apply_status: str
    graph_degraded: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

