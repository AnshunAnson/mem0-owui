from __future__ import annotations

from app.adapters.mem0_adapter import Mem0Adapter
from app.config import Settings


def build_settings() -> Settings:
    return Settings(
        llm_api_base="http://host.docker.internal:1234/v1",
        llm_api_key="sk-local",
        llm_model="qwen3.5-9b",
        embedding_model="text-embedding-bge-m3",
        embedding_model_dims=1024,
        qdrant_host="qdrant",
        qdrant_port=6333,
        neo4j_url="neo4j://neo4j:7687",
        neo4j_username="neo4j",
        neo4j_password="neo4j_password",
    )


def test_build_config_without_graph_uses_openai_base_url_and_dimensions() -> None:
    adapter = Mem0Adapter(build_settings())

    config = adapter._build_config(enable_graph=False)

    assert config["llm"]["config"]["openai_base_url"] == "http://host.docker.internal:1234/v1"
    assert config["embedder"]["config"]["embedding_dims"] == 1024
    assert config["vector_store"]["config"]["embedding_model_dims"] == 1024
    assert "graph_store" not in config


def test_build_config_with_graph_adds_graph_store() -> None:
    adapter = Mem0Adapter(build_settings())

    config = adapter._build_config(enable_graph=True)

    assert config["graph_store"]["provider"] == "neo4j"
    assert config["graph_store"]["config"]["url"] == "neo4j://neo4j:7687"
