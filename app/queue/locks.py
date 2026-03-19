"""Redis-backed serialization locks."""

from __future__ import annotations

from contextlib import contextmanager

from redis import Redis

from app.config import Settings


def build_lock_key(scope: dict[str, str], target_id: str | None) -> str:
    if target_id:
        return f"memory-apply:target:{target_id}"
    return f"memory-apply:scope:{scope['user_id']}:{scope['project_id']}"


@contextmanager
def apply_lock(redis_client: Redis, settings: Settings, scope: dict[str, str], target_id: str | None):
    lock_key = build_lock_key(scope, target_id)
    lock = redis_client.lock(
        lock_key,
        timeout=settings.redis_lock_timeout_seconds,
        blocking_timeout=settings.redis_lock_blocking_timeout_seconds,
    )
    acquired = lock.acquire(blocking=True)
    if not acquired:
        raise TimeoutError(f"Unable to acquire apply lock: {lock_key}")
    try:
        yield lock_key
    finally:
        lock.release()

