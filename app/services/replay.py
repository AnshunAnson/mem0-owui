"""Replay orchestration."""

from __future__ import annotations

from app.queue.jobs import enqueue_process_event
from app.store import queries


def replay_event(settings, event_id: str, mode: str) -> dict:
    event = queries.get_event(settings, event_id)
    if event is None:
        raise KeyError(f"Event not found: {event_id}")
    queries.force_update_event_status(settings, event_id, "queued", last_error=None, next_retry_at=None)
    enqueue_process_event(settings, event_id, mode=mode)
    return queries.get_event(settings, event_id)
