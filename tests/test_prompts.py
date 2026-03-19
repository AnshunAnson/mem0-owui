from __future__ import annotations

import json

from app.schemas.candidates import ExtractResult, MemoryCandidate
from app.services import audit, evolution


def test_evolve_prompt_allows_json_examples_during_formatting() -> None:
    prompt = evolution._prompt_text("evolve_memory.txt").format(
        existing_memories=json.dumps([{"id": "mem-1", "memory": "likes coffee"}], ensure_ascii=False, indent=2),
        new_memory=json.dumps(
            ExtractResult(type="preference", content="likes black coffee", confidence=0.9).model_dump(),
            ensure_ascii=False,
            indent=2,
        ),
    )

    assert '"action":"create|update|merge|link|discard"' in prompt
    assert '"content": "likes black coffee"' in prompt


def test_audit_prompt_allows_json_examples_during_formatting() -> None:
    prompt = audit._prompt_text("audit_memory.txt").format(
        candidate=json.dumps(
            MemoryCandidate(action="create", memory="likes black coffee", confidence=0.9).model_dump(),
            ensure_ascii=False,
            indent=2,
        ),
        existing_memories=json.dumps([{"id": "mem-1", "memory": "likes coffee"}], ensure_ascii=False, indent=2),
        scope=json.dumps({"user_id": "u1", "project_id": "p1", "task_id": "t1"}, ensure_ascii=False, indent=2),
    )

    assert '"decision":"approved|revised|rejected"' in prompt
    assert '"memory": "likes black coffee"' in prompt
