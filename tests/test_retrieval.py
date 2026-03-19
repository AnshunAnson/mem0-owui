from __future__ import annotations

from app.config import Settings
from app.services.retrieval import retrieve_context


class FakeMem0Adapter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def search_scope(self, *, query, scope, limit, filters, prefer_graph):
        self.calls.append(
            {
                "query": query,
                "scope": scope,
                "limit": limit,
                "filters": filters,
                "prefer_graph": prefer_graph,
            }
        )

        if filters == {"scope_project_id": "p1", "scope_task_id": "t1"}:
            return (
                [
                    {"id": "shared", "memory": "task memory", "score": 0.9, "metadata": {}},
                    {"id": "task-only", "memory": "task-only detail", "score": 0.8, "metadata": {}},
                ],
                False,
            )
        if filters == {"scope_project_id": "p1"}:
            return (
                [
                    {"id": "shared", "memory": "project duplicate", "score": 0.7, "metadata": {}},
                    {"id": "project-only", "memory": "project detail", "score": 0.6, "metadata": {}},
                ],
                True,
            )
        return (
            [
                {
                    "id": "user-only",
                    "memory": "u" * 80,
                    "score": 0.2,
                    "metadata": {},
                }
            ],
            False,
        )


def build_settings() -> Settings:
    return Settings(
        retrieval_top_k=6,
        retrieval_max_memories=3,
        retrieval_max_chars_per_memory=20,
        retrieval_max_total_chars=60,
    )


def test_retrieve_context_merges_task_project_user_scopes_and_dedupes() -> None:
    adapter = FakeMem0Adapter()
    settings = build_settings()

    result = retrieve_context(
        settings,
        adapter,
        query="remember this",
        scope={"user_id": "u1", "project_id": "p1", "task_id": "t1"},
    )

    assert [call["filters"] for call in adapter.calls] == [
        {"scope_project_id": "p1", "scope_task_id": "t1"},
        {"scope_project_id": "p1"},
        None,
    ]
    assert result["graph_degraded"] is True
    assert [item["id"] for item in result["memories"]] == ["shared", "task-only", "project-only"]
    assert result["injected_context"].startswith("Relevant memories:\n")
    assert "project duplicate" not in result["injected_context"]


def test_retrieve_context_respects_prompt_budget() -> None:
    adapter = FakeMem0Adapter()
    settings = build_settings()
    settings = settings.model_copy(
        update={
            "retrieval_max_memories": 2,
            "retrieval_max_chars_per_memory": 10,
            "retrieval_max_total_chars": 25,
        }
    )

    result = retrieve_context(
        settings,
        adapter,
        query="remember this",
        scope={"user_id": "u1", "project_id": "p1", "task_id": "t1"},
    )

    assert len(result["memories"]) == 2
    assert result["memories"][0]["memory"] == "task me..."
    assert result["memories"][1]["memory"] == "task-on..."
    assert "project detail" not in result["injected_context"]
