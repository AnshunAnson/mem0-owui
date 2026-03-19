"""Retrieval budget helpers."""

from __future__ import annotations

from typing import Iterable

from app.config import Settings


def truncate_text(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def format_memories_for_prompt(memories: Iterable[dict], settings: Settings) -> tuple[str, list[dict]]:
    selected: list[dict] = []
    lines: list[str] = []
    total_chars = 0
    for item in memories:
        if len(selected) >= settings.retrieval_max_memories:
            break
        memory_text = truncate_text(str(item.get("memory", "")), settings.retrieval_max_chars_per_memory)
        if not memory_text:
            continue
        candidate_total = total_chars + len(memory_text)
        if lines and candidate_total > settings.retrieval_max_total_chars:
            break
        label = item.get("scope_level", "user")
        selected_item = dict(item)
        selected_item["memory"] = memory_text
        selected.append(selected_item)
        lines.append(f"- [{label}] {memory_text}")
        total_chars = candidate_total
    if not lines:
        return "", []
    context = "Relevant memories:\n" + "\n".join(lines)
    return context, selected

