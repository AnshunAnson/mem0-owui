from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.hashing import build_apply_id, build_dedupe_key


def test_dedupe_key_is_stable_inside_window() -> None:
    when = datetime(2026, 3, 19, 10, 0, tzinfo=UTC)
    payload = {
        "conversation_id": "chat-1",
        "messages": [{"role": "user", "content": "hello"}],
        "assistant_response": "world",
        "scope": {"user_id": "u1", "project_id": "p1", "task_id": "t1"},
        "source": "openwebui_pipeline",
        "window_seconds": 300,
    }
    first = build_dedupe_key(when=when, **payload)
    second = build_dedupe_key(when=when + timedelta(minutes=4), **payload)
    assert first == second


def test_dedupe_key_rolls_after_window() -> None:
    when = datetime(2026, 3, 19, 10, 0, tzinfo=UTC)
    payload = {
        "conversation_id": "chat-1",
        "messages": [{"role": "user", "content": "hello"}],
        "assistant_response": "world",
        "scope": {"user_id": "u1", "project_id": "p1", "task_id": "t1"},
        "source": "openwebui_pipeline",
        "window_seconds": 300,
    }
    first = build_dedupe_key(when=when, **payload)
    later = build_dedupe_key(when=when + timedelta(minutes=6), **payload)
    assert first != later


def test_apply_id_is_stable() -> None:
    first = build_apply_id("event-1", "candidate-1", "create", "target-1")
    second = build_apply_id("event-1", "candidate-1", "create", "target-1")
    assert first == second

