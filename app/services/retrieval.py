"""Retrieval service for thin pipeline inlet."""

from __future__ import annotations

from app.budgets import format_memories_for_prompt
from app.config import Settings
from app.logging import get_logger

LOGGER = get_logger(__name__)


def build_retrieval_filters(scope: dict[str, str], scope_level: str) -> dict[str, str] | None:
    if scope_level == "task":
        return {
            "scope_project_id": scope["project_id"],
            "scope_task_id": scope["task_id"],
        }
    if scope_level == "project":
        return {
            "scope_project_id": scope["project_id"],
        }
    return None


def retrieve_context(settings: Settings, mem0_adapter, query: str, scope: dict[str, str]) -> dict:
    collected: list[dict] = []
    graph_degraded = False
    seen_ids: set[str] = set()

    for scope_level in ("task", "project", "user"):
        filters = build_retrieval_filters(scope, scope_level)
        results, degraded = mem0_adapter.search_scope(
            query=query,
            scope=scope,
            limit=settings.retrieval_top_k,
            filters=filters,
            prefer_graph=True,
        )
        graph_degraded = graph_degraded or degraded
        for item in results:
            memory_id = item.get("id")
            if memory_id and memory_id in seen_ids:
                continue
            metadata = item.get("metadata") or {}
            item["scope_level"] = scope_level
            freshness = 1.0 if scope_level == "task" else 0.6 if scope_level == "project" else 0.3
            item["combined_score"] = float(item.get("score") or 0.0) + freshness
            if memory_id:
                seen_ids.add(memory_id)
            collected.append(item)

    collected.sort(key=lambda item: item.get("combined_score", 0.0), reverse=True)
    injected_context, selected = format_memories_for_prompt(collected, settings)
    return {
        "injected_context": injected_context,
        "memories": selected,
        "graph_degraded": graph_degraded,
    }

