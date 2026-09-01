"""Repeatable isolated performance profile for Gate 8B crawler orchestration.

It deliberately uses no school network traffic.  Two fixture sources each expose
one list page and three details with deterministic latency.  The first pass
emulates the previous serial full-detail check; the second uses the runtime's
concurrent, incremental pass against the same SQLite data.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.crawler.runner as runner_module
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Source
from app.schemas.notice import NoticeCandidate


class TimedFixtureSource:
    def __init__(self, code: str) -> None:
        self.code = code
        self.items = [
            NoticeCandidate(title=f"{code} notice {number}", url=f"https://{code}.test/{number}")
            for number in range(3)
        ]

    async def fetch_list(self) -> list[NoticeCandidate]:
        await asyncio.sleep(0.02)
        return self.items

    async def fetch_detail(self, item: NoticeCandidate) -> NoticeCandidate:
        await asyncio.sleep(0.03)
        return item.model_copy(update={"content": f"fixture body {item.url}"})

    async def close(self) -> None:
        return None


async def main() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    db = sessions()
    configs = [
        {"code": code, "name": code, "base_url": f"https://{code}.test", "enabled": True}
        for code in ("alpha", "beta")
    ]
    db.add_all([Source(code=item["code"], name=item["name"], base_url=item["base_url"]) for item in configs])
    db.commit()
    adapters = {item["code"]: TimedFixtureSource(item["code"]) for item in configs}
    original_session, original_build, original_init, original_yaml = (
        runner_module.SessionLocal,
        runner_module.build_source,
        runner_module.init_db,
        runner_module.load_yaml,
    )
    runner_module.SessionLocal = sessions
    runner_module.build_source = lambda config: adapters[config["code"]]
    runner_module.init_db = lambda: None
    runner_module.load_yaml = lambda name: (
        {"sources": configs} if name == "sources.yaml" else {"crawler": {"source_concurrency": 2}}
    )
    try:
        with tempfile.TemporaryDirectory() as directory:
            manager = CrawlerManager(cache_dir=Path(directory))
            before_started = time.perf_counter()
            before_results = [await manager._run_source(config, False) for config in configs]
            before_seconds = time.perf_counter() - before_started
            after_started = time.perf_counter()
            after_result = await manager.run()
            after_seconds = time.perf_counter() - after_started
    finally:
        runner_module.SessionLocal = original_session
        runner_module.build_source = original_build
        runner_module.init_db = original_init
        runner_module.load_yaml = original_yaml
        db.close()
        engine.dispose()
    print(
        "before "
        f"total={before_seconds:.3f}s list_pages=2 detail_fetches={sum(item.detail_fetched for item in before_results)} "
        f"list={sum(item.list_duration_seconds for item in before_results):.3f}s "
        f"detail={sum(item.detail_duration_seconds for item in before_results):.3f}s "
        f"parse_db={sum(item.parse_db_duration_seconds for item in before_results):.3f}s"
    )
    print(
        "after "
        f"total={after_seconds:.3f}s list_pages=2 detail_fetches={sum(item.detail_fetched for item in after_result.source_results)} "
        f"unchanged_skipped={sum(item.detail_skipped for item in after_result.source_results)} "
        f"list={sum(item.list_duration_seconds for item in after_result.source_results):.3f}s "
        f"detail={sum(item.detail_duration_seconds for item in after_result.source_results):.3f}s "
        f"parse_db={sum(item.parse_db_duration_seconds for item in after_result.source_results):.3f}s"
    )


if __name__ == "__main__":
    asyncio.run(main())
