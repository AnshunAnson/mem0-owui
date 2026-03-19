"""Repair worker process."""

from __future__ import annotations

from rq import Worker

from app.config import get_settings
from app.logging import configure_logging
from app.queue.redis import get_redis_client


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    redis_client = get_redis_client(settings.redis_url)
    worker = Worker([settings.repair_queue_name], connection=redis_client)
    worker.work()


if __name__ == "__main__":
    main()
