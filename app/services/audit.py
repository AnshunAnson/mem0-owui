"""Audit step."""

from __future__ import annotations

import json
from pathlib import Path

from app import constants
from app.schemas.audits import AuditResult
from app.schemas.candidates import MemoryCandidate


def _prompt_text(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "prompts" / name).read_text(encoding="utf-8")


def _build_create_candidate(candidate: MemoryCandidate) -> MemoryCandidate:
    data = candidate.model_dump()
    data["action"] = constants.ACTION_CREATE
    data["target_id"] = None
    data["reason"] = (data.get("reason") or "") + " revised_to_create"
    return MemoryCandidate(**data)


def audit_memory_candidate(
    llm_client,
    *,
    candidate: MemoryCandidate,
    existing_memories: list[dict],
    scope: dict[str, str],
    target_exists: bool,
    confidence_threshold: float,
) -> AuditResult:
    if candidate.action == constants.ACTION_DISCARD:
        return AuditResult(
            decision=constants.AUDIT_REJECTED,
            final_action=constants.ACTION_DISCARD,
            audit_reason="candidate_discarded",
        )

    if candidate.confidence <= confidence_threshold or not candidate.memory.strip():
        return AuditResult(
            decision=constants.AUDIT_REJECTED,
            final_action=constants.ACTION_DISCARD,
            audit_reason="low_confidence_or_empty_memory",
        )

    if candidate.action in {constants.ACTION_UPDATE, constants.ACTION_MERGE, constants.ACTION_LINK} and not target_exists:
        revised = _build_create_candidate(candidate)
        return AuditResult(
            decision=constants.AUDIT_REVISED,
            final_action=constants.ACTION_CREATE,
            revised_candidate=revised,
            audit_reason="missing_stable_target_id",
        )

    prompt = _prompt_text("audit_memory.txt").format(
        candidate=json.dumps(candidate.model_dump(), ensure_ascii=False, indent=2),
        existing_memories=json.dumps(existing_memories, ensure_ascii=False, indent=2),
        scope=json.dumps(scope, ensure_ascii=False, indent=2),
    )
    result = llm_client.chat_json(system_prompt=prompt, user_prompt="Return the audit JSON now.")
    decision = str(result.get("decision", constants.AUDIT_APPROVED))
    if decision not in constants.AUDIT_DECISIONS:
        decision = constants.AUDIT_APPROVED
    final_action = str(result.get("final_action", candidate.action))
    if final_action not in constants.ACTIONS:
        final_action = candidate.action
    revised_payload = result.get("revised_candidate")
    revised_candidate = None
    if isinstance(revised_payload, dict):
        try:
            revised_candidate = MemoryCandidate(**revised_payload)
        except Exception:
            revised_candidate = None
    if decision == constants.AUDIT_REVISED and revised_candidate is None:
        revised_candidate = _build_create_candidate(candidate)
        final_action = revised_candidate.action
    if final_action in {constants.ACTION_UPDATE, constants.ACTION_MERGE, constants.ACTION_LINK}:
        checked_candidate = revised_candidate or candidate
        if not checked_candidate.target_id:
            revised_candidate = _build_create_candidate(checked_candidate)
            decision = constants.AUDIT_REVISED
            final_action = constants.ACTION_CREATE
    return AuditResult(
        decision=decision,
        final_action=final_action,
        revised_candidate=revised_candidate,
        audit_reason=str(result.get("audit_reason", "")).strip(),
    )

