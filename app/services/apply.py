"""Apply step."""

from __future__ import annotations

from app import constants
from app.hashing import build_apply_id
from app.queue.jobs import enqueue_repair_event
from app.queue.locks import apply_lock
from app.queue.redis import get_redis_client
from app.schemas.audits import AuditResult
from app.schemas.candidates import MemoryCandidate
from app.store import queries


def apply_memory_action(
    settings,
    *,
    mem0_adapter,
    event: dict,
    candidate_record: dict,
    audit_result: AuditResult,
) -> dict | None:
    if audit_result.final_action == constants.ACTION_DISCARD or audit_result.decision == constants.AUDIT_REJECTED:
        return None

    candidate_payload = audit_result.revised_candidate.model_dump() if audit_result.revised_candidate else candidate_record["candidate"]
    candidate = MemoryCandidate(**candidate_payload)
    apply_id = build_apply_id(
        event_id=event["event_id"],
        candidate_hash=candidate_record["candidate_hash"],
        final_action=audit_result.final_action,
        target_id=candidate.target_id,
    )
    existing_apply = queries.get_apply(settings, apply_id)
    if existing_apply is not None:
        return existing_apply

    redis_client = get_redis_client(settings.redis_url)
    with apply_lock(redis_client, settings, event["scope"], candidate.target_id):
        existing_apply = queries.get_apply(settings, apply_id)
        if existing_apply is not None:
            return existing_apply

        if audit_result.final_action in {constants.ACTION_UPDATE, constants.ACTION_MERGE}:
            if not candidate.target_id or mem0_adapter.get_existing_memory(candidate.target_id) is None:
                raise ValueError("Update or merge requires a stable mem0 target_id")
            write_result = mem0_adapter.update_memory(memory_id=candidate.target_id, text=candidate.memory)
        else:
            metadata = mem0_adapter.build_memory_metadata(
                scope=event["scope"],
                source_event_id=event["event_id"],
                confidence=candidate.confidence,
                memory_kind=candidate.memory_kind,
                relations=candidate.relations,
                target_id=candidate.target_id,
            )
            write_result = mem0_adapter.add_memory(
                text=candidate.memory,
                scope=event["scope"],
                metadata=metadata,
            )

        apply_row = queries.insert_apply(
            settings,
            apply_id=apply_id,
            event_id=event["event_id"],
            candidate_id=candidate_record["candidate_id"],
            final_action=audit_result.final_action,
            target_id=candidate.target_id,
            mem0_memory_id=write_result.get("mem0_memory_id"),
            apply_status=constants.STATUS_APPLIED,
            graph_degraded=bool(write_result.get("graph_degraded")),
        )
        if apply_row["graph_degraded"] and candidate.relations and apply_row.get("mem0_memory_id"):
            enqueue_repair_event(settings, event["event_id"], apply_row["apply_id"])
        return apply_row

