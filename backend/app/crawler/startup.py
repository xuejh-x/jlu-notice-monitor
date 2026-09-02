from __future__ import annotations

import logging
from typing import Any

from app.crawler.runner import CrawlerAlreadyRunning, CrawlerManager, crawler_manager
from app.logging_config import log_event

logger = logging.getLogger(__name__)


class StartupSyncCoordinator:
    """Process-local, idempotent Desktop startup synchronization trigger."""

    def __init__(self, crawler: CrawlerManager) -> None:
        self.crawler = crawler
        self.triggered = False
        self.outcome: str | None = None

    def trigger_once(self) -> bool:
        if self.triggered:
            return False
        self.triggered = True
        try:
            self.crawler.start(trigger="startup")
        except CrawlerAlreadyRunning:
            self.outcome = "skipped_running"
            log_event(logger, logging.INFO, "startup_sync_skipped", status=self.outcome)
        else:
            self.outcome = "started"
            log_event(logger, logging.INFO, "startup_sync_started", trigger_source="startup")
        return True

    def status(self) -> dict[str, Any]:
        return {"triggered": self.triggered, "outcome": self.outcome}


startup_sync = StartupSyncCoordinator(crawler_manager)
