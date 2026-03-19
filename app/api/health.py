"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.adapters.llm_openai import OpenAICompatibleClient
from app.adapters.mem0_adapter import Mem0Adapter
from app.adapters.qdrant_health import check_qdrant
from app.api.deps import get_app_settings, get_llm_client, get_mem0_adapter
from app.config import Settings
from app.queue.redis import get_redis_client
from app.schemas.api import DependencyStatus, ReadyResponse
from app.store.sqlite import connect

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, bool]:
    return {"status": True}


@router.get("/ready", response_model=ReadyResponse)
def ready(
    settings: Settings = Depends(get_app_settings),
    llm_client: OpenAICompatibleClient = Depends(get_llm_client),
    mem0_adapter: Mem0Adapter = Depends(get_mem0_adapter),
) -> ReadyResponse:
    dependencies: list[DependencyStatus] = []

    try:
        connection = connect(settings)
        connection.execute("SELECT 1").fetchone()
        connection.close()
        sqlite_ok, sqlite_detail = True, str(settings.sqlite_path)
    except Exception as exc:
        sqlite_ok, sqlite_detail = False, str(exc)
    dependencies.append(DependencyStatus(name="sqlite", ok=sqlite_ok, detail=sqlite_detail))

    try:
        redis_client = get_redis_client(settings.redis_url)
        redis_client.ping()
        redis_ok, redis_detail = True, settings.redis_url
    except Exception as exc:
        redis_ok, redis_detail = False, str(exc)
    dependencies.append(DependencyStatus(name="redis", ok=redis_ok, detail=redis_detail))

    qdrant_ok, qdrant_detail = check_qdrant(settings)
    dependencies.append(DependencyStatus(name="qdrant", ok=qdrant_ok, detail=qdrant_detail))

    neo4j_ok, neo4j_detail = mem0_adapter.graph_adapter.readiness()
    dependencies.append(DependencyStatus(name="neo4j", ok=neo4j_ok, detail=neo4j_detail))

    llm_ok, llm_detail = llm_client.readiness()
    dependencies.append(DependencyStatus(name="llm", ok=llm_ok, detail=llm_detail))

    try:
        mem0_adapter.get_existing_memory("noop")
        mem0_ok, mem0_detail = True, "adapter_initialized"
    except Exception as exc:
        mem0_ok, mem0_detail = False, str(exc)
    dependencies.append(DependencyStatus(name="mem0", ok=mem0_ok, detail=mem0_detail))

    minimum_ready = sqlite_ok and redis_ok
    return ReadyResponse(ready=minimum_ready, minimum_ready=minimum_ready, dependencies=dependencies)

