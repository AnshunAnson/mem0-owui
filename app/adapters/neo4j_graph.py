"""Neo4j graph operations used for repair and readiness."""

from __future__ import annotations

from datetime import UTC, datetime
from socket import create_connection
from urllib.parse import urlparse

from neo4j import GraphDatabase

from app.config import Settings


class Neo4jGraphAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def readiness(self) -> tuple[bool, str]:
        parsed = urlparse(self.settings.neo4j_url.replace("neo4j://", "bolt://"))
        host = parsed.hostname or "neo4j"
        port = parsed.port or 7687
        try:
            with create_connection((host, port), timeout=self.settings.neo4j_ready_timeout_seconds):
                return True, f"reachable:{host}:{port}"
        except Exception as exc:
            return False, str(exc)

    def write_relations(self, memory_id: str, relations: list[dict]) -> bool:
        if not relations:
            return True
        driver = GraphDatabase.driver(
            self.settings.neo4j_url,
            auth=(self.settings.neo4j_username, self.settings.neo4j_password),
        )
        timestamp = datetime.now(UTC).isoformat()
        try:
            with driver.session() as session:
                for relation in relations:
                    relation_name = str(relation.get("name") or relation.get("target") or relation.get("value") or "").strip()
                    if not relation_name:
                        continue
                    relation_type = str(relation.get("type") or relation.get("relation") or "RELATED").upper()
                    session.run(
                        """
                        MERGE (m:Memory {id: $memory_id})
                        MERGE (c:Concept {name: $concept_name})
                        MERGE (m)-[r:RELATED {type: $relation_type}]->(c)
                        ON CREATE SET r.created_at = $timestamp
                        SET r.updated_at = $timestamp
                        """,
                        memory_id=memory_id,
                        concept_name=relation_name,
                        relation_type=relation_type,
                        timestamp=timestamp,
                    )
            return True
        finally:
            driver.close()

