from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from app.crawler.runner import CrawlRunResult, CrawlerAlreadyRunning, CrawlerManager, crawler_manager, utcnow
from app.logging_config import log_event

logger = logging.getLogger(__name__)


class StartupSyncCoordinator:
    """Process-local, idempotent Desktop startup synchronization trigger."""

    def __init__(self, crawler: CrawlerManager) -> None:
        self.crawler = crawler
        self.triggered = False
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.outcome: str | None = None
        self.skipped_reason: str | None = None

    def trigger_once(self) -> bool:
        if self.triggered:
            return False
        self.triggered = True
        self.started_at = utcnow()
        try:
            task = self.crawler.start(trigger="startup")
        except CrawlerAlreadyRunning:
            self.outcome = "skipped_running"
            self.skipped_reason = "crawler_already_running"
            self.completed_at = utcnow()
            log_event(logger, logging.INFO, "startup_sync_skipped", status=self.outcome)
        except Exception as exc:
            # Startup synchronization is best-effort background work. A launch
            # failure must never make the API/Desktop readiness lifecycle fail.
            self.outcome = "failure"
            self.completed_at = utcnow()
            log_event(
                logger,
                logging.ERROR,
                "startup_sync_failed",
                status=self.outcome,
                error_type=type(exc).__name__,
            )
        else:
            self.outcome = "started"
            task.add_done_callback(self._record_completion)
            log_event(logger, logging.INFO, "startup_sync_started", trigger_source="startup")
        return True

    def _record_completion(self, task: asyncio.Task[CrawlRunResult]) -> None:
        self.completed_at = utcnow()
        try:
            result = task.result()
        except asyncio.CancelledError:
            self.outcome = "cancelled"
        except Exception as exc:
            self.outcome = "failure"
            log_event(
                logger,
                logging.ERROR,
                "startup_sync_failed",
                status=self.outcome,
                error_type=type(exc).__name__,
            )
        else:
            self.outcome = result.status
            log_event(logger, logging.INFO, "startup_sync_finished", status=self.outcome)

    def status(self) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outcome": self.outcome,
            "skipped_reason": self.skipped_reason,
        }


startup_sync = StartupSyncCoordinator(crawler_manager)
