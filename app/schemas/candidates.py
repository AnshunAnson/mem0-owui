"""Candidate schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app import constants


class ExtractResult(BaseModel):
    type: str
    content: str
    confidence: float
    tags: list[str] = Field(default_factory=list)
    memory_kind: str = constants.MEMORY_KIND_EPHEMERAL


class MemoryCandidate(BaseModel):
    action: str
    target_id: str | None = None
    memory: str
    relations: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""
    memory_kind: str = constants.MEMORY_KIND_EPHEMERAL
    confidence: float = 0.0
    candidate_schema_version: str = constants.CANDIDATE_SCHEMA_VERSION


class CandidateRecord(BaseModel):
    candidate_id: str
    event_id: str
    candidate_version: int
    candidate_hash: str
    candidate: MemoryCandidate
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

