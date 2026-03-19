"""Repair service."""

from __future__ import annotations

from app.store import queries


def repair_graph_relations(settings, repair_adapter, event_id: str, apply_id: str) -> bool:
    apply_row = queries.get_apply(settings, apply_id)
    candidate_record = queries.get_latest_candidate(settings, event_id)
    if apply_row is None or candidate_record is None:
        return False
    relations = candidate_record["candidate"].get("relations", [])
    memory_id = apply_row.get("mem0_memory_id")
    return repair_adapter.repair_relations(memory_id, relations)
