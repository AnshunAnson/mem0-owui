"""Event schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app import constants


class ScopeContext(BaseModel):
    user_id: str
    project_id: str = "default"
    task_id: str = "default"


class ConversationMessage(BaseModel):
    role: str
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    elif "text" in item:
                        parts.append(str(item["text"]))
                elif item is not None:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        if value is None:
            return ""
        return str(value)


class MemoryEventCreate(BaseModel):
    event_id: str
    conversation_id: str
    user_id: str
    scope: ScopeContext
    messages: list[ConversationMessage]
    assistant_response: str
    source: str = "openwebui_pipeline"
    event_schema_version: str = constants.EVENT_SCHEMA_VERSION
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryEventFilters(BaseModel):
    status: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    scope_project_id: str | None = None
    scope_task_id: str | None = None
    limit: int = 50
    offset: int = 0


class ReplayRequest(BaseModel):
    mode: Literal["logical", "full"] = constants.REPLAY_LOGICAL


class RetrievalRequest(BaseModel):
    query: str
    scope: ScopeContext
