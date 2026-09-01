from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
import app.crawler.scheduler as scheduler_module
from app.config import Settings
from app.crawler.runner import CrawlerAlreadyRunning, CrawlerManager, SourceRunResult
from app.database import Base
from app.crawler.scheduler import CrawlerScheduler, SchedulerConfig


class FakeCrawler:
    def __init__(self, *, delay: float = 0, outcomes: list[str] | None = None) -> None:
        self.delay = delay
        self.outcomes = outcomes or ["success"]
        self.calls: list[str] = []
        self.running = False
        self.raise_running = False

    def start(self, *, trigger: str):
        if self.running or self.raise_running:
            raise CrawlerAlreadyRunning("crawler is already running")
        self.calls.append(trigger)

        async def run():
            self.running = True
            try:
                await asyncio.sleep(self.delay)
                outcome = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
                if outcome == "exception":
                    raise RuntimeError("fixture failure")
                return SimpleNamespace(status=outcome)
            finally:
                self.running = False

        return asyncio.create_task(run())


async def wait_until(predicate, timeout: float = 0.2) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not reached")
        await asyncio.sleep(0.002)


@pytest.mark.asyncio
async def test_enabled_scheduler_runs_repeatedly_and_reports_next_run() -> None:
    crawler = FakeCrawler()
    scheduler = CrawlerScheduler(
        crawler, SchedulerConfig(enabled=True, interval_minutes=1), interval_seconds=0.01
    )
    scheduler.start()
    try:
        await wait_until(lambda: len(crawler.calls) >= 2)
        status = scheduler.status()
        assert all(call == "scheduled" for call in crawler.calls)
        assert status["last_scheduled_outcome"] == "success"
        assert status["next_scheduled_run"] is not None
    finally:
        await scheduler.shutdown()
    assert scheduler.status()["running"] is False
    assert scheduler.status()["next_scheduled_run"] is None


@pytest.mark.asyncio
async def test_disabled_scheduler_never_starts() -> None:
    crawler = FakeCrawler()
    scheduler = CrawlerScheduler(crawler, SchedulerConfig(enabled=False, interval_minutes=1))
    scheduler.start()
    await asyncio.sleep(0)
    assert crawler.calls == []
    assert scheduler.status()["running"] is False


@pytest.mark.asyncio
async def test_scheduler_can_restart_cleanly() -> None:
    crawler = FakeCrawler()
    scheduler = CrawlerScheduler(
        crawler, SchedulerConfig(enabled=True, interval_minutes=1), interval_seconds=0.01
    )
    scheduler.start()
    await wait_until(lambda: len(crawler.calls) == 1)
    await scheduler.shutdown()
    scheduler.start()
    await wait_until(lambda: len(crawler.calls) >= 2)
    await scheduler.shutdown()
    assert scheduler.status()["running"] is False


@pytest.mark.asyncio
async def test_long_running_crawl_does_not_queue_overlapping_runs() -> None:
    crawler = FakeCrawler(delay=0.04)
    scheduler = CrawlerScheduler(
        crawler, SchedulerConfig(enabled=True, interval_minutes=1), interval_seconds=0.01
    )
    scheduler.start()
    await asyncio.sleep(0.055)
    assert len(crawler.calls) == 1
    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_manual_collision_is_skipped_and_scheduler_recovers() -> None:
    crawler = FakeCrawler()
    crawler.raise_running = True
    scheduler = CrawlerScheduler(
        crawler, SchedulerConfig(enabled=True, interval_minutes=1), interval_seconds=0.01
    )
    scheduler.start()
    try:
        await wait_until(lambda: scheduler.status()["last_scheduled_outcome"] == "skipped_running")
        crawler.raise_running = False
        await wait_until(lambda: len(crawler.calls) >= 1)
        assert all(call == "scheduled" for call in crawler.calls)
    finally:
        await scheduler.shutdown()


@pytest.mark.asyncio
async def test_failure_and_partial_failure_are_retained_in_scheduler_status() -> None:
    crawler = FakeCrawler(outcomes=["partial_failure", "exception"])
    scheduler = CrawlerScheduler(
        crawler, SchedulerConfig(enabled=True, interval_minutes=1), interval_seconds=0.01
    )
    scheduler.start()
    try:
        await wait_until(lambda: scheduler.status()["last_scheduled_outcome"] == "failure")
        assert "fixture failure" in (scheduler.status()["last_error"] or "")
    finally:
        await scheduler.shutdown()


def test_invalid_scheduler_configuration_fails_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scheduler_module, "load_yaml", lambda _: {"crawler": {"scheduler": {"enabled": True, "interval_minutes": 0}}}
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(ValueError, match="interval_minutes"):
        SchedulerConfig.load()


@pytest.mark.asyncio
async def test_short_interval_runtime_uses_the_real_crawler_lock(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An isolated runtime check: scheduled execution goes through CrawlerManager."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    manager = CrawlerManager(cache_dir=tmp_path)
    configs = [{"code": "fixture", "name": "Fixture", "base_url": "https://fixture.test", "enabled": True}]
    monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(runner_module, "init_db", lambda: None)
    monkeypatch.setattr(
        runner_module,
        "load_yaml",
        lambda name: {"sources": configs} if name == "sources.yaml" else {"crawler": {"source_concurrency": 1}},
    )

    async def run_source(config, bootstrap):
        await asyncio.sleep(0.02)
        return SourceRunResult(source=config["code"], status="success")

    monkeypatch.setattr(manager, "_run_source", run_source)
    scheduler = CrawlerScheduler(
        manager, SchedulerConfig(enabled=True, interval_minutes=1), interval_seconds=0.01
    )
    scheduler.start()
    try:
        await wait_until(lambda: manager.running)
        assert manager.status()["trigger_source"] == "scheduled"
        await wait_until(lambda: scheduler.status()["last_scheduled_outcome"] == "success")
        assert manager.last_trigger == "scheduled"
        assert scheduler.status()["next_scheduled_run"] is not None
    finally:
        await scheduler.shutdown()
        await manager.shutdown()
        db.close()
        engine.dispose()
