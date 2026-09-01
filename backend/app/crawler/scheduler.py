from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.config import get_settings, load_yaml
from app.crawler.runner import CrawlerAlreadyRunning, CrawlerManager, crawler_manager, utcnow
from app.logging_config import log_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool
    interval_minutes: int

    @classmethod
    def load(cls) -> "SchedulerConfig":
        raw = load_yaml("settings.yaml").get("crawler", {}).get("scheduler", {})
        settings = get_settings()
        enabled = settings.scheduler_enabled if settings.scheduler_enabled is not None else raw.get("enabled", True)
        interval = settings.scheduler_interval_minutes or raw.get("interval_minutes", 15)
        if not isinstance(enabled, bool):
            raise ValueError("crawler.scheduler.enabled must be a boolean")
        if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1:
            raise ValueError("crawler.scheduler.interval_minutes must be an integer >= 1")
        return cls(enabled=enabled, interval_minutes=interval)


class CrawlerScheduler:
    """No-backlog scheduler: each interval starts after the previous run ends."""

    def __init__(
        self, crawler: CrawlerManager, config: SchedulerConfig | None = None, *, interval_seconds: float | None = None
    ) -> None:
        self.crawler = crawler
        self.config = config or SchedulerConfig.load()
        self._interval_seconds = interval_seconds or self.config.interval_minutes * 60
        if self._interval_seconds <= 0:
            raise ValueError("scheduler interval must be positive")
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.last_scheduled_run: datetime | None = None
        self.next_scheduled_run: datetime | None = None
        self.last_scheduled_outcome: str | None = None
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running or not self.config.enabled:
            return
        self._stop.clear()
        self.next_scheduled_run = utcnow() + timedelta(seconds=self._interval_seconds)
        self._task = asyncio.create_task(self._run(), name="crawler-scheduler")
        log_event(logger, logging.INFO, "scheduler_started", interval_minutes=self.config.interval_minutes)

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
        self.next_scheduled_run = None
        log_event(logger, logging.INFO, "scheduler_stopped")

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "running": self.running,
            "interval_minutes": self.config.interval_minutes,
            "last_scheduled_run": self.last_scheduled_run,
            "next_scheduled_run": self.next_scheduled_run,
            "last_scheduled_outcome": self.last_scheduled_outcome,
            "last_error": self.last_error,
        }

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval_seconds)
                break
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set():
                break
            self.last_scheduled_run = utcnow()
            log_event(logger, logging.INFO, "scheduler_triggered", trigger_source="scheduled")
            try:
                task = self.crawler.start(trigger="scheduled")
            except CrawlerAlreadyRunning:
                self.last_scheduled_outcome = "skipped_running"
                log_event(logger, logging.WARNING, "scheduler_run_skipped", status="skipped_running")
            else:
                try:
                    result = await task
                    self.last_scheduled_outcome = result.status
                    self.last_error = None
                    log_event(logger, logging.INFO, "scheduler_run_finished", status=result.status)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_scheduled_outcome = "failure"
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    log_event(logger, logging.ERROR, "scheduler_run_failed", status="failure", error_type=type(exc).__name__, error=str(exc))
            if not self._stop.is_set():
                self.next_scheduled_run = utcnow() + timedelta(seconds=self._interval_seconds)


scheduler_manager = CrawlerScheduler(crawler_manager)
