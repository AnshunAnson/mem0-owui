"""RQ task implementations."""

from __future__ import annotations

import uuid

from app import constants
from app.adapters.llm_openai import OpenAICompatibleClient
from app.adapters.mem0_adapter import Mem0Adapter
from app.adapters.repair_adapter import RepairAdapter
from app.config import get_settings
from app.hashing import build_candidate_hash
from app.schemas.candidates import MemoryCandidate
from app.services.apply import apply_memory_action
from app.services.audit import audit_memory_candidate
from app.services.evolution import evolve_memory
from app.services.extraction import extract_memory
from app.services.repair import repair_graph_relations
from app.store import queries


def process_event_job(event_id: str, mode: str = constants.REPLAY_LOGICAL) -> dict:
    settings = get_settings()
    llm_client = OpenAICompatibleClient(settings)
    mem0_adapter = Mem0Adapter(settings)

    event = queries.get_event(settings, event_id)
    if event is None:
        raise KeyError(f"Event not found: {event_id}")

    if mode == constants.REPLAY_FULL or queries.get_latest_candidate(settings, event_id) is None:
        if event["status"] == constants.STATUS_QUEUED:
            queries.update_event_status(settings, event_id, constants.STATUS_EXTRACTING)
        extract_result = extract_memory(llm_client, event["payload"])
        existing_memories, _ = mem0_adapter.search_scope(
            query=extract_result.content or event["payload"]["assistant_response"],
            scope=event["scope"],
            limit=5,
            filters={"scope_project_id": event["scope"]["project_id"]},
            prefer_graph=True,
        )
        candidate = evolve_memory(llm_client, existing_memories, extract_result)
        candidate_hash = build_candidate_hash(candidate.model_dump())
        candidate_record = queries.insert_candidate(
            settings,
            candidate_id=str(uuid.uuid4()),
            event_id=event_id,
            candidate_version=queries.get_next_candidate_version(settings, event_id),
            candidate_hash=candidate_hash,
            candidate=candidate.model_dump(),
            candidate_schema_version=candidate.candidate_schema_version,
        )
        if event["status"] == constants.STATUS_EXTRACTING:
            queries.update_event_status(settings, event_id, constants.STATUS_CANDIDATE_READY)
    else:
        candidate_record = queries.get_latest_candidate(settings, event_id)
        existing_memories, _ = mem0_adapter.search_scope(
            query=candidate_record["candidate"]["memory"],
            scope=event["scope"],
            limit=5,
            filters={"scope_project_id": event["scope"]["project_id"]},
            prefer_graph=True,
        )
        current_status = queries.get_event(settings, event_id)["status"]
        if current_status == constants.STATUS_QUEUED:
            queries.force_update_event_status(settings, event_id, constants.STATUS_CANDIDATE_READY)

    candidate_model = MemoryCandidate(**candidate_record["candidate"])
    current_status = queries.get_event(settings, event_id)["status"]
    if current_status == constants.STATUS_CANDIDATE_READY:
        queries.update_event_status(settings, event_id, constants.STATUS_AUDITING)

    target_exists = True
    if candidate_model.action in {constants.ACTION_UPDATE, constants.ACTION_MERGE, constants.ACTION_LINK}:
        target_exists = mem0_adapter.get_existing_memory(candidate_model.target_id or "") is not None

    audit_result = audit_memory_candidate(
        llm_client,
        candidate=candidate_model,
        existing_memories=existing_memories,
        scope=event["scope"],
        target_exists=target_exists,
        confidence_threshold=settings.memory_confidence_threshold,
    )
    queries.insert_audit(
        settings,
        audit_id=str(uuid.uuid4()),
        event_id=event_id,
        candidate_id=candidate_record["candidate_id"],
        audit_result=audit_result.decision,
        audit_payload=audit_result.model_dump(),
        audit_schema_version=audit_result.audit_schema_version,
    )

    current_status = queries.get_event(settings, event_id)["status"]
    if current_status == constants.STATUS_AUDITING:
        next_status = {
            constants.AUDIT_APPROVED: constants.STATUS_APPROVED,
            constants.AUDIT_REVISED: constants.STATUS_REVISED,
            constants.AUDIT_REJECTED: constants.STATUS_REJECTED,
        }[audit_result.decision]
        queries.update_event_status(settings, event_id, next_status)

    if audit_result.decision == constants.AUDIT_REJECTED or audit_result.final_action == constants.ACTION_DISCARD:
        current_status = queries.get_event(settings, event_id)["status"]
        if current_status == constants.STATUS_REJECTED:
            queries.update_event_status(settings, event_id, constants.STATUS_DISCARDED)
        return {"event_id": event_id, "status": constants.STATUS_DISCARDED}

    current_status = queries.get_event(settings, event_id)["status"]
    if current_status in {constants.STATUS_APPROVED, constants.STATUS_REVISED}:
        queries.update_event_status(settings, event_id, constants.STATUS_APPLYING)
    apply_row = apply_memory_action(
        settings,
        mem0_adapter=mem0_adapter,
        event=event,
        candidate_record=candidate_record,
        audit_result=audit_result,
    )
    current_status = queries.get_event(settings, event_id)["status"]
    if current_status == constants.STATUS_APPLYING:
        queries.update_event_status(settings, event_id, constants.STATUS_APPLIED)
    return {"event_id": event_id, "status": constants.STATUS_APPLIED, "apply": apply_row}


def repair_graph_job(event_id: str, apply_id: str) -> dict:
    settings = get_settings()
    repair_adapter = RepairAdapter(Mem0Adapter(settings).graph_adapter)
    repaired = repair_graph_relations(settings, repair_adapter, event_id, apply_id)
    return {"event_id": event_id, "apply_id": apply_id, "repaired": repaired}
