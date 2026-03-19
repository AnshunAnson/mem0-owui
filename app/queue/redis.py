"""Redis and RQ helpers."""

from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import Settings


@lru_cache(maxsize=4)
def get_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url)


def get_queue(settings: Settings, queue_name: str) -> Queue:
    return Queue(queue_name, connection=get_redis_client(settings.redis_url))

