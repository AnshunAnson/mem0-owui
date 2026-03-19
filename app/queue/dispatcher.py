"""Dispatcher loop for retryable events."""

from __future__ import annotations

import threading
import time

from app import constants
from app.config import Settings
from app.logging import get_logger
from app.queue.jobs import enqueue_process_event
from app.store import queries

LOGGER = get_logger(__name__)


class Dispatcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="memory-dispatcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.dispatch_once()
            except Exception as exc:
                LOGGER.exception("Dispatcher loop failure: %s", exc)
            self._stop.wait(self.settings.dispatcher_interval_seconds)

    def dispatch_once(self) -> int:
        events = queries.get_retryable_events(
            self.settings,
            statuses=(constants.STATUS_RECEIVED, constants.STATUS_QUEUE_FAILED),
            limit=100,
        )
        dispatched = 0
        for event in events:
            try:
                enqueue_process_event(self.settings, event["event_id"])
                queries.update_event_status(self.settings, event["event_id"], constants.STATUS_QUEUED)
                dispatched += 1
            except Exception as exc:
                LOGGER.warning("Failed to dispatch event %s: %s", event["event_id"], exc)
                queries.schedule_retry(
                    self.settings,
                    event["event_id"],
                    last_error=str(exc),
                    delay_seconds=self.settings.retry_backoff_seconds,
                )
        return dispatched
