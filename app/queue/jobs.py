"""RQ enqueue helpers."""

from __future__ import annotations

from rq import Retry

from app.config import Settings
from app.queue.redis import get_queue


PROCESS_EVENT_JOB = "app.worker.tasks.process_event_job"
REPAIR_EVENT_JOB = "app.worker.tasks.repair_graph_job"


def enqueue_process_event(settings: Settings, event_id: str, mode: str = "logical") -> str:
    queue = get_queue(settings, settings.main_queue_name)
    job = queue.enqueue(
        PROCESS_EVENT_JOB,
        event_id,
        mode=mode,
        retry=Retry(max=settings.max_retry_count, interval=[30, 60, 120]),
    )
    return job.id


def enqueue_repair_event(settings: Settings, event_id: str, apply_id: str) -> str:
    queue = get_queue(settings, settings.repair_queue_name)
    job = queue.enqueue(
        REPAIR_EVENT_JOB,
        event_id,
        apply_id=apply_id,
        retry=Retry(max=settings.max_retry_count, interval=[60, 180, 300]),
    )
    return job.id

