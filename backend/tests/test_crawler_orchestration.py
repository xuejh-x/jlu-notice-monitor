from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
from app.crawler.runner import CrawlerAlreadyRunning, CrawlerManager, SourceRunResult
from app.database import Base
from app.models import Notice, Source
from app.schemas.notice import NoticeCandidate


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class FixtureSource:
    def __init__(self, items: list[NoticeCandidate], details: dict[str, NoticeCandidate]) -> None:
        self.items = items
        self.details = details
        self.detail_calls: list[str] = []

    async def fetch_list(self) -> list[NoticeCandidate]:
        return self.items

    async def fetch_detail(self, item: NoticeCandidate) -> NoticeCandidate:
        self.detail_calls.append(item.url)
        return self.details[item.url]

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_incremental_skip_new_updated_unchanged_and_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = CrawlerManager(cache_dir=Path(".") / ".pytest-crawler")
    with make_session() as db:
        source = Source(code="fixture", name="Fixture", base_url="https://example.test")
        db.add(source)
        db.commit()
        first = NoticeCandidate(title="Original", url="https://example.test/1", content="first")
        changed_list = NoticeCandidate(title="Changed title", url="https://example.test/1", content="")
        new_item = NoticeCandidate(title="New", url="https://example.test/2", content="")
        adapter = FixtureSource([first], {first.url: first})
        monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(runner_module, "build_source", lambda _: adapter)
        config = {"code": "fixture", "name": "Fixture", "base_url": "https://example.test"}

        first_run = await manager._run_source(config, False)
        assert first_run.status == "success"
        assert first_run.new_count == 1 and first_run.detail_fetched == 1

        unchanged_run = await manager._run_source(config, False)
        assert unchanged_run.unchanged_count == 1
        assert unchanged_run.detail_skipped == 1
        assert adapter.detail_calls == [first.url]

        adapter.items = [changed_list, new_item]
        changed_detail = changed_list.model_copy(update={"content": "changed body"})
        adapter.details = {changed_list.url: changed_detail, new_item.url: new_item.model_copy(update={"content": "new body"})}
        update_run = await manager._run_source(config, False)
        assert update_run.updated_count == 1 and update_run.new_count == 1
        assert update_run.detail_fetched == 2
        assert len(db.scalars(select(Notice)).all()) == 2


@pytest.mark.asyncio
async def test_source_failure_is_isolated_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = CrawlerManager(cache_dir=Path(".") / ".pytest-crawler")
    with make_session() as db:
        source = Source(code="fixture", name="Fixture", base_url="https://example.test")
        db.add(source)
        db.commit()

        class TimeoutSource(FixtureSource):
            async def fetch_list(self) -> list[NoticeCandidate]:
                raise asyncio.TimeoutError("timed out")

        monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(runner_module, "build_source", lambda _: TimeoutSource([], {}))
        result = await manager._run_source(
            {"code": "fixture", "name": "Fixture", "base_url": "https://example.test"}, False
        )
        assert result.status == "failure"
        assert "TimeoutError" in result.errors[0]
        assert db.scalar(select(Source.last_error).where(Source.code == "fixture"))


@pytest.mark.asyncio
async def test_bad_detail_is_partial_failure_but_healthy_items_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = CrawlerManager(cache_dir=Path(".") / ".pytest-crawler")
    with make_session() as db:
        source = Source(code="fixture", name="Fixture", base_url="https://example.test")
        db.add(source)
        db.commit()

        class ParseFailureSource(FixtureSource):
            async def fetch_detail(self, item: NoticeCandidate) -> NoticeCandidate:
                if item.url.endswith("bad"):
                    raise ValueError("malformed HTML")
                return item.model_copy(update={"content": "good body"})

        good = NoticeCandidate(title="Good", url="https://example.test/good")
        bad = NoticeCandidate(title="Bad", url="https://example.test/bad")
        monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            runner_module, "build_source", lambda _: ParseFailureSource([good, bad], {})
        )
        result = await manager._run_source(
            {"code": "fixture", "name": "Fixture", "base_url": "https://example.test"}, False
        )
        assert result.status == "partial_failure"
        assert result.new_count == 1 and len(result.errors) == 1
        assert len(db.scalars(select(Notice)).all()) == 1
        assert "malformed HTML" in (db.scalar(select(Source.last_error)) or "")


@pytest.mark.asyncio
async def test_limited_concurrent_run_rejects_duplicate_and_exposes_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = CrawlerManager(cache_dir=tmp_path)
    configs = [
        {"code": "one", "name": "One", "base_url": "https://one.test", "enabled": True},
        {"code": "two", "name": "Two", "base_url": "https://two.test", "enabled": True},
    ]
    session = make_session()
    monkeypatch.setattr(runner_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(runner_module, "init_db", lambda: None)
    monkeypatch.setattr(
        runner_module,
        "load_yaml",
        lambda name: {"sources": configs} if name == "sources.yaml" else {"crawler": {"source_concurrency": 2}},
    )
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_source(config: dict[str, str], _: bool) -> SourceRunResult:
        entered.set()
        await release.wait()
        return SourceRunResult(source=config["code"], status="success", unchanged_count=1)

    monkeypatch.setattr(manager, "_run_source", slow_source)
    task = asyncio.create_task(manager.run())
    await entered.wait()
    assert manager.status()["status"] == "running"
    assert manager.status()["total_sources"] == 2
    with pytest.raises(CrawlerAlreadyRunning):
        await manager.run()
    release.set()
    result = await task
    assert result.status == "success"
    assert result.unchanged_count == 2
    assert manager.status()["status"] == "success"
    session.close()
