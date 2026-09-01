from __future__ import annotations

import asyncio
from contextlib import nullcontext
from io import StringIO
from pathlib import Path
from typing import cast

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.__main__ import _watch_managed_stdin, build_parser
from app.crawler.runner import CrawlRunResult, CrawlerManager
from app.config import Settings
from app.database import Base, get_db
from app.main import app
import app.main as main_module
from app.paths import (
    BACKEND_DIR,
    ensure_runtime_directories,
    get_app_data_dir,
    get_cache_dir,
    get_database_path,
    get_log_dir,
    get_oa_profile_dir,
    get_runtime_config_dir,
)


def test_development_and_production_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_app_data_dir("development") == BACKEND_DIR
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert get_app_data_dir("production") == tmp_path / "Local" / "JLU Notice Monitor"


def test_runtime_directory_override_stays_in_temp_dir(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    ensure_runtime_directories("production", runtime)
    assert get_database_path("production", runtime) == runtime / "data" / "notices.db"
    assert get_log_dir("production", runtime).is_dir()
    assert get_oa_profile_dir("production", runtime).is_dir()
    assert get_cache_dir("production", runtime).is_dir()
    assert get_runtime_config_dir("production", runtime).is_dir()
    settings = Settings(
        _env_file=None,
        environment="production",
        app_data_dir=str(runtime),
        database_url=None,
    )
    assert settings.database_path == runtime / "data" / "notices.db"


def test_tauri_production_origin_is_allowed_by_default() -> None:
    settings = Settings(_env_file=None)
    assert "http://tauri.localhost" in settings.cors_origins


def test_health_checks_database() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "jlu-notice-monitor"
        assert response.json()["version"] == "0.2.0"
        assert response.json()["database"] == "ok"
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_health_reports_database_failure() -> None:
    class BrokenSession:
        def execute(self, *_: object, **__: object) -> None:
            raise RuntimeError("database unavailable")

    def override_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/health")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
        assert response.json()["database"] == "error"
        assert "unavailable" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_crawler_status_exposes_scheduler_runtime() -> None:
    response = TestClient(app).get("/api/crawler/status")
    assert response.status_code == 200
    scheduler = response.json()["scheduler"]
    assert scheduler["enabled"] is True
    assert scheduler["interval_minutes"] == 15
    assert scheduler["next_scheduled_run"] is None


def test_server_host_and_port_cli() -> None:
    args = build_parser().parse_args(["serve", "--host", "127.0.0.1", "--port", "8765"])
    assert args.host == "127.0.0.1"
    assert args.port == 8765


def test_managed_server_cli_flag() -> None:
    args = build_parser().parse_args(["serve", "--managed"])
    assert args.managed is True


def test_managed_stdin_requests_graceful_exit_on_command_or_eof() -> None:
    class ServerStub:
        should_exit = False

    server = ServerStub()
    _watch_managed_stdin(cast(uvicorn.Server, server), StringIO("ignored\nshutdown\n"))
    assert server.should_exit is True

    server.should_exit = False
    _watch_managed_stdin(cast(uvicorn.Server, server), StringIO(""))
    assert server.should_exit is True


@pytest.mark.asyncio
async def test_crawler_background_task_is_cancelled_on_shutdown(tmp_path: Path) -> None:
    manager = CrawlerManager(cache_dir=tmp_path)
    manager._task = cast(asyncio.Task[CrawlRunResult], asyncio.create_task(asyncio.sleep(60)))
    await manager.shutdown()
    assert manager._task is None


@pytest.mark.asyncio
async def test_lifespan_starts_scheduler_and_stops_it_before_crawler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class Scheduler:
        def start(self) -> None:
            events.append("scheduler-start")

        async def shutdown(self) -> None:
            events.append("scheduler-stop")

    class Crawler:
        def _sync_sources(self, *_: object) -> None:
            events.append("sync-sources")

        async def shutdown(self) -> None:
            events.append("crawler-stop")

    monkeypatch.setattr(main_module, "scheduler_manager", Scheduler())
    monkeypatch.setattr(main_module, "crawler_manager", Crawler())
    monkeypatch.setattr(main_module, "ensure_runtime_directories", lambda *_: None)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(main_module, "load_yaml", lambda _: {"sources": []})
    async with main_module.lifespan(app):
        assert events == ["sync-sources", "scheduler-start"]
    assert events == ["sync-sources", "scheduler-start", "scheduler-stop", "crawler-stop"]
