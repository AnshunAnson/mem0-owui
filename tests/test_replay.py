from __future__ import annotations

from app import constants
from app.config import get_settings
from app.store import queries
from app.store.migrations import run_migrations


def test_apply_idempotency(sqlite_path) -> None:
    settings = get_settings()
    run_migrations(settings)
    queries.create_event(
        settings,
        event_id="event-1",
        dedupe_key="dedupe-1",
        conversation_id="chat-1",
        user_id="u1",
        scope={"user_id": "u1", "project_id": "p1", "task_id": "t1"},
        payload={"messages": [], "assistant_response": "ok"},
        status=constants.STATUS_RECEIVED,
        event_schema_version="1.0",
    )
    queries.insert_candidate(
        settings,
        candidate_id="candidate-1",
        event_id="event-1",
        candidate_version=1,
        candidate_hash="candidate-hash",
        candidate={"action": "create", "memory": "prefers tea", "relations": [], "reason": "", "memory_kind": "preference", "confidence": 0.9},
        candidate_schema_version="1.0",
    )
    first = queries.insert_apply(
        settings,
        apply_id="apply-1",
        event_id="event-1",
        candidate_id="candidate-1",
        final_action="create",
        target_id=None,
        mem0_memory_id="mem-1",
        apply_status="applied",
        graph_degraded=False,
    )
    second = queries.insert_apply(
        settings,
        apply_id="apply-1",
        event_id="event-1",
        candidate_id="candidate-1",
        final_action="create",
        target_id=None,
        mem0_memory_id="mem-1",
        apply_status="applied",
        graph_degraded=False,
    )
    assert first["apply_id"] == second["apply_id"]
    latest = queries.get_latest_apply(settings, "event-1")
    assert latest["apply_id"] == "apply-1"
