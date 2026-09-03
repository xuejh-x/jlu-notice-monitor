from __future__ import annotations

import asyncio
import logging

from app.database import SessionLocal
from app.logging_config import log_event
from app.services.notifications import generate_scheduled_events

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """Local no-backlog clock for deadline and daily-summary event generation."""

    def __init__(self, *, interval_seconds: float = 60.0) -> None:
        self.interval_seconds = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="notification-scheduler")

    async def shutdown(self) -> None:
        self._stop.set()
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None

    def generate_once(self) -> int:
        with SessionLocal() as db:
            events = generate_scheduled_events(db)
            db.commit()
            return len(events)

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                created = self.generate_once()
                if created:
                    log_event(logger, logging.INFO, "notification_events_generated", count=created)
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    "notification_scheduler_failed",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass


notification_scheduler = NotificationScheduler()
