from __future__ import annotations

from app import constants
from app.config import get_settings
from app.schemas.events import MemoryEventFilters
from app.store import queries
from app.store.migrations import run_migrations
from app.store.sqlite import connect


def test_sqlite_pragmas_and_round_trip(sqlite_path) -> None:
    settings = get_settings()
    run_migrations(settings)

    connection = connect(settings)
    try:
        journal_mode = connection.execute("PRAGMA journal_mode;").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous;").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout;").fetchone()[0]
    finally:
        connection.close()

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) == 5000
    assert int(synchronous) in {1, 2}

    created = queries.create_event(
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
    assert created["event_id"] == "event-1"

    updated = queries.update_event_status(settings, "event-1", constants.STATUS_QUEUED)
    assert updated["status"] == constants.STATUS_QUEUED

    items, total = queries.list_events(settings, MemoryEventFilters())
    assert total == 1
    assert items[0]["event_id"] == "event-1"

