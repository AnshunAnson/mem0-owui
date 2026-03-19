from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.store.migrations import run_migrations


def test_event_lifecycle_api(sqlite_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.ingestion.enqueue_process_event", lambda settings, event_id, mode="logical": "job-1")
    monkeypatch.setattr("app.services.replay.enqueue_process_event", lambda settings, event_id, mode="logical": "job-2")

    from app.config import get_settings

    settings = get_settings()
    run_migrations(settings)
    client = TestClient(create_app())

    payload = {
        "event_id": "event-1",
        "conversation_id": "chat-1",
        "user_id": "u1",
        "scope": {"user_id": "u1", "project_id": "p1", "task_id": "t1"},
        "messages": [{"role": "user", "content": "hello"}],
        "assistant_response": "world",
        "source": "openwebui_pipeline",
        "event_schema_version": "1.0",
    }

    response = client.post("/memory/events", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"

    list_response = client.get("/memory/events")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    detail_response = client.get("/memory/events/event-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["event"]["event_id"] == "event-1"

    replay_response = client.post("/memory/events/event-1/replay", json={"mode": "logical"})
    assert replay_response.status_code == 202

