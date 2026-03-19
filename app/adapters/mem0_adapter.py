"""mem0 wrapper with vector-only fallback and stable target handling."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mem0 import Memory

from app import constants
from app.adapters.neo4j_graph import Neo4jGraphAdapter
from app.config import Settings


class Mem0Adapter:
    COLLECTION_NAME = "mem0"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._memory_with_graph: Memory | None = None
        self._memory_vector_only: Memory | None = None
        self.graph_adapter = Neo4jGraphAdapter(settings)

    def search_scope(
        self,
        *,
        query: str,
        scope: dict[str, str],
        limit: int,
        filters: dict[str, Any] | None = None,
        prefer_graph: bool = True,
    ) -> tuple[list[dict[str, Any]], bool]:
        graph_degraded = False
        try:
            memory = self._get_memory(enable_graph=prefer_graph)
            result = memory.search(
                query=query,
                user_id=scope["user_id"],
                limit=limit,
                filters=filters,
                rerank=True,
            )
        except Exception:
            graph_degraded = prefer_graph
            memory = self._get_memory(enable_graph=False)
            result = memory.search(
                query=query,
                user_id=scope["user_id"],
                limit=limit,
                filters=filters,
                rerank=True,
            )
        return self._normalize_search_results(result), graph_degraded

    def get_existing_memory(self, memory_id: str) -> dict[str, Any] | None:
        if not memory_id:
            return None
        try:
            return self._get_memory(enable_graph=False).get(memory_id)
        except Exception:
            return None

    def add_memory(
        self,
        *,
        text: str,
        scope: dict[str, str],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        payload = [{"role": "user", "content": text}]
        try:
            result = self._get_memory(enable_graph=True).add(
                payload,
                user_id=scope["user_id"],
                metadata=metadata,
                infer=False,
            )
            graph_degraded = False
        except Exception:
            result = self._get_memory(enable_graph=False).add(
                payload,
                user_id=scope["user_id"],
                metadata=metadata,
                infer=False,
            )
            graph_degraded = True
        results = self._normalize_search_results(result)
        mem0_memory_id = results[0]["id"] if results else None
        return {
            "mem0_memory_id": mem0_memory_id,
            "graph_degraded": graph_degraded,
            "results": results,
        }

    def update_memory(self, *, memory_id: str, text: str) -> dict[str, Any]:
        self._get_memory(enable_graph=False).update(memory_id, text)
        return {"mem0_memory_id": memory_id, "graph_degraded": False}

    def build_memory_metadata(
        self,
        *,
        scope: dict[str, str],
        source_event_id: str,
        confidence: float,
        memory_kind: str,
        relations: list[dict[str, Any]],
        target_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        metadata = {
            "scope.user_id": scope["user_id"],
            "scope.project_id": scope["project_id"],
            "scope.task_id": scope["task_id"],
            "scope_user_id": scope["user_id"],
            "scope_project_id": scope["project_id"],
            "scope_task_id": scope["task_id"],
            "source_event_id": source_event_id,
            "created_at": now,
            "last_seen_at": now,
            "decay_score": 1.0,
            "confidence": confidence,
            "memory_kind": memory_kind,
            "memory_metadata_version": constants.MEMORY_METADATA_VERSION,
            "relations": relations,
        }
        if target_id:
            metadata["target_id"] = target_id
        return metadata

    def _normalize_search_results(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            items = payload.get("results") or payload.get("memories") or []
        elif isinstance(payload, list):
            items = payload
        else:
            items = []
        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") or {}
            normalized.append(
                {
                    "id": item.get("id") or item.get("memory_id"),
                    "memory": item.get("memory") or item.get("text") or item.get("content"),
                    "score": item.get("score", 0.0),
                    "metadata": metadata,
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                }
            )
        return normalized

    def _get_memory(self, *, enable_graph: bool) -> Memory:
        if enable_graph:
            if self._memory_with_graph is None:
                self._memory_with_graph = Memory.from_config(self._build_config(enable_graph=True))
            return self._memory_with_graph
        if self._memory_vector_only is None:
            self._memory_vector_only = Memory.from_config(self._build_config(enable_graph=False))
        return self._memory_vector_only

    def _build_config(self, *, enable_graph: bool) -> dict[str, Any]:
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": self.COLLECTION_NAME,
                    "embedding_model_dims": self.settings.embedding_model_dims,
                    "host": self.settings.qdrant_host,
                    "port": self.settings.qdrant_port,
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": self.settings.llm_api_key,
                    "model": self.settings.llm_model,
                    "openai_base_url": self.settings.llm_api_base,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "api_key": self.settings.llm_api_key,
                    "model": self.settings.embedding_model,
                    "embedding_dims": self.settings.embedding_model_dims,
                    "openai_base_url": self.settings.llm_api_base,
                },
            },
        }
        if enable_graph:
            config["graph_store"] = {
                "provider": "neo4j",
                "config": {
                    "url": self.settings.neo4j_url,
                    "username": self.settings.neo4j_username,
                    "password": self.settings.neo4j_password,
                },
            }
        return config
