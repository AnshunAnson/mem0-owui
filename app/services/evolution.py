"""Evolution step."""

from __future__ import annotations

import json
from pathlib import Path

from app import constants
from app.schemas.candidates import ExtractResult, MemoryCandidate


def _prompt_text(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "prompts" / name).read_text(encoding="utf-8")


def evolve_memory(llm_client, existing_memories: list[dict], extract_result: ExtractResult) -> MemoryCandidate:
    if extract_result.type == "noise":
        return MemoryCandidate(
            action=constants.ACTION_DISCARD,
            memory="",
            reason="noise",
            memory_kind=extract_result.memory_kind,
            confidence=extract_result.confidence,
        )

    prompt = _prompt_text("evolve_memory.txt").format(
        existing_memories=json.dumps(existing_memories, ensure_ascii=False, indent=2),
        new_memory=json.dumps(extract_result.model_dump(), ensure_ascii=False, indent=2),
    )
    result = llm_client.chat_json(system_prompt=prompt, user_prompt="Return the candidate JSON now.")
    action = str(result.get("action", constants.ACTION_DISCARD))
    if action not in constants.ACTIONS:
        action = constants.ACTION_DISCARD
    target_id = str(result.get("target_id") or "").strip() or None
    memory = str(result.get("memory") or extract_result.content).strip()
    relations = result.get("relations") if isinstance(result.get("relations"), list) else []
    reason = str(result.get("reason", "")).strip()
    memory_kind = str(result.get("memory_kind") or extract_result.memory_kind)
    if memory_kind not in constants.MEMORY_KINDS:
        memory_kind = extract_result.memory_kind
    return MemoryCandidate(
        action=action,
        target_id=target_id,
        memory=memory,
        relations=relations,
        reason=reason,
        memory_kind=memory_kind,
        confidence=float(result.get("confidence", extract_result.confidence) or extract_result.confidence),
    )

