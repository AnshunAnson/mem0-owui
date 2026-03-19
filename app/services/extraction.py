"""Extraction step."""

from __future__ import annotations

import json
from pathlib import Path

from app import constants
from app.schemas.candidates import ExtractResult


def _prompt_text(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "prompts" / name).read_text(encoding="utf-8")


def classify_memory_kind(memory_type: str) -> str:
    if memory_type == "preference":
        return constants.MEMORY_KIND_PREFERENCE
    if memory_type in {"correction", "fact"}:
        return constants.MEMORY_KIND_FACT
    if memory_type == "routine":
        return constants.MEMORY_KIND_WORKFLOW
    return constants.MEMORY_KIND_EPHEMERAL


def extract_memory(llm_client, event_payload: dict) -> ExtractResult:
    prompt = _prompt_text("extract_memory.txt")
    conversation = json.dumps(event_payload["messages"], ensure_ascii=False, indent=2)
    result = llm_client.chat_json(system_prompt=prompt, user_prompt=f"Conversation:\n{conversation}")
    memory_type = str(result.get("type", "noise"))
    content = str(result.get("content", "")).strip()
    confidence = float(result.get("confidence", 0.0) or 0.0)
    tags = [str(tag) for tag in result.get("tags", []) if tag]
    if not content:
        memory_type = "noise"
        confidence = 0.0
    return ExtractResult(
        type=memory_type,
        content=content,
        confidence=confidence,
        tags=tags,
        memory_kind=classify_memory_kind(memory_type),
    )

