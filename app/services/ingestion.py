"""Event ingestion service."""

from __future__ import annotations

from datetime import UTC, datetime

from app import constants
from app.config import Settings
from app.hashing import build_dedupe_key
from app.queue.jobs import enqueue_process_event
from app.schemas.events import MemoryEventCreate
from app.store import queries


def ingest_event(settings: Settings, event_in: MemoryEventCreate) -> dict:
    existing_by_id = queries.get_event(settings, event_in.event_id)
    if existing_by_id is not None:
        return existing_by_id

    received_at = datetime.now(UTC)
    normalized_payload = event_in.model_dump(mode="json")
    dedupe_key = build_dedupe_key(
        conversation_id=event_in.conversation_id,
        messages=[message.model_dump() for message in event_in.messages],
        assistant_response=event_in.assistant_response,
        scope=event_in.scope.model_dump(),
        source=event_in.source,
        window_seconds=settings.dedupe_window_seconds,
        when=received_at,
    )
    existing_by_dedupe = queries.get_event_by_dedupe_key(settings, dedupe_key)
    if existing_by_dedupe is not None:
        return existing_by_dedupe

    event = queries.create_event(
        settings,
        event_id=event_in.event_id,
        dedupe_key=dedupe_key,
        conversation_id=event_in.conversation_id,
        user_id=event_in.user_id,
        scope=event_in.scope.model_dump(),
        payload=normalized_payload,
        status=constants.STATUS_RECEIVED,
        event_schema_version=event_in.event_schema_version,
    )
    try:
        enqueue_process_event(settings, event["event_id"])
        event = queries.update_event_status(settings, event["event_id"], constants.STATUS_QUEUED)
    except Exception as exc:
        event = queries.schedule_retry(
            settings,
            event["event_id"],
            last_error=str(exc),
            delay_seconds=settings.retry_backoff_seconds,
        )
    return event

