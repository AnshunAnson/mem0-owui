"""Environment-backed settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "mem0-owui-governance"
    app_env: str = "development"
    log_level: str = "INFO"

    sqlite_path: Path = Field(default=Path("./data/memory_governance.db"))
    dispatcher_interval_seconds: int = 10
    dedupe_window_seconds: int = 300
    max_retry_count: int = 5
    retry_backoff_seconds: int = 30

    redis_url: str = "redis://redis:6379/0"
    main_queue_name: str = "memory-events"
    repair_queue_name: str = "memory-repair"

    llm_api_base: str = "http://host.docker.internal:1234/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen3.5-9b"
    llm_timeout_seconds: int = 30
    embedding_model: str = "text-embedding-bge-m3"
    embedding_model_dims: int = 1024

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    neo4j_url: str = "neo4j://neo4j:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "neo4j_password"

    retrieval_timeout_ms: int = 600
    retrieval_top_k: int = 6
    retrieval_max_memories: int = 6
    retrieval_max_chars_per_memory: int = 300
    retrieval_max_total_chars: int = 1200
    memory_confidence_threshold: float = 0.7

    redis_lock_timeout_seconds: int = 60
    redis_lock_blocking_timeout_seconds: int = 10

    internal_api_host: str = "0.0.0.0"
    internal_api_port: int = 8081

    qdrant_http_timeout_seconds: int = 2
    llm_ready_timeout_seconds: int = 2
    neo4j_ready_timeout_seconds: int = 2
    mem0_user_id_fallback: str = "default_user"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
