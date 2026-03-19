"""Dependency wiring."""

from __future__ import annotations

from functools import lru_cache

from app.adapters.llm_openai import OpenAICompatibleClient
from app.adapters.mem0_adapter import Mem0Adapter
from app.adapters.neo4j_graph import Neo4jGraphAdapter
from app.adapters.repair_adapter import RepairAdapter
from app.config import Settings, get_settings


@lru_cache(maxsize=1)
def get_llm_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(get_settings())


@lru_cache(maxsize=1)
def get_mem0_adapter() -> Mem0Adapter:
    return Mem0Adapter(get_settings())


@lru_cache(maxsize=1)
def get_graph_adapter() -> Neo4jGraphAdapter:
    return Neo4jGraphAdapter(get_settings())


@lru_cache(maxsize=1)
def get_repair_adapter() -> RepairAdapter:
    return RepairAdapter(get_graph_adapter())


def get_app_settings() -> Settings:
    return get_settings()

