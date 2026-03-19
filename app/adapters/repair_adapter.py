"""Graph-only repair adapter."""

from __future__ import annotations

from app.adapters.neo4j_graph import Neo4jGraphAdapter


class RepairAdapter:
    def __init__(self, graph_adapter: Neo4jGraphAdapter):
        self.graph_adapter = graph_adapter

    def repair_relations(self, memory_id: str, relations: list[dict]) -> bool:
        if not memory_id or not relations:
            return True
        return self.graph_adapter.write_relations(memory_id, relations)

