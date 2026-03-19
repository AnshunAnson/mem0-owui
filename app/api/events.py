"""Event endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_app_settings
from app.config import Settings
from app.schemas.api import EventDetailResponse, EventIngestResponse, EventListResponse, EventSummary
from app.schemas.events import MemoryEventCreate, MemoryEventFilters, ReplayRequest
from app.services.ingestion import ingest_event
from app.services.replay import replay_event
from app.store import queries

router = APIRouter(prefix="/memory/events", tags=["events"])


@router.post("", response_model=EventIngestResponse, status_code=202)
def post_event(event_in: MemoryEventCreate, settings: Settings = Depends(get_app_settings)) -> EventIngestResponse:
    event = ingest_event(settings, event_in)
    return EventIngestResponse(
        event_id=event["event_id"],
        dedupe_key=event["dedupe_key"],
        status=event["status"],
    )


@router.get("", response_model=EventListResponse)
def list_events(
    status: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    scope_project_id: str | None = Query(default=None),
    scope_task_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_app_settings),
) -> EventListResponse:
    filters = MemoryEventFilters(
        status=status,
        user_id=user_id,
        conversation_id=conversation_id,
        scope_project_id=scope_project_id,
        scope_task_id=scope_task_id,
        limit=limit,
        offset=offset,
    )
    items, total = queries.list_events(settings, filters)
    summaries = [
        EventSummary(
            event_id=item["event_id"],
            conversation_id=item["conversation_id"],
            user_id=item["user_id"],
            status=item["status"],
            retry_count=item["retry_count"],
            last_error=item["last_error"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
        for item in items
    ]
    return EventListResponse(items=summaries, total=total)


@router.get("/{event_id}", response_model=EventDetailResponse)
def get_event(event_id: str, settings: Settings = Depends(get_app_settings)) -> EventDetailResponse:
    event = queries.get_event(settings, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventDetailResponse(
        event=event,
        candidate=queries.get_latest_candidate(settings, event_id),
        audit=queries.get_latest_audit(settings, event_id),
        apply=queries.get_latest_apply(settings, event_id),
        timeline=queries.build_timeline(settings, event_id),
    )


@router.post("/{event_id}/replay", status_code=202)
def post_replay(event_id: str, replay: ReplayRequest, settings: Settings = Depends(get_app_settings)) -> dict[str, str]:
    try:
        replay_event(settings, event_id, replay.mode)
    except KeyError:
        raise HTTPException(status_code=404, detail="Event not found") from None
    return {"event_id": event_id, "mode": replay.mode, "status": "queued"}

