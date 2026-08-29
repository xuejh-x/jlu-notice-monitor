from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.__main__ import build_parser
from app.crawler.runner import CrawlRunResult, CrawlerManager
from app.config import Settings
from app.database import Base, get_db
from app.main import app
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


def test_server_host_and_port_cli() -> None:
    args = build_parser().parse_args(["serve", "--host", "127.0.0.1", "--port", "8765"])
    assert args.host == "127.0.0.1"
    assert args.port == 8765


@pytest.mark.asyncio
async def test_crawler_background_task_is_cancelled_on_shutdown(tmp_path: Path) -> None:
    manager = CrawlerManager(cache_dir=tmp_path)
    manager._task = cast(asyncio.Task[CrawlRunResult], asyncio.create_task(asyncio.sleep(60)))
    await manager.shutdown()
    assert manager._task is None
