from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.logging_config import configure_logging, log_event
from app.main import app
from app.models import Source
from app.paths import get_log_dir


def test_production_log_path_uses_runtime_data_directory(tmp_path: Path) -> None:
    assert get_log_dir("production", tmp_path) == tmp_path / "logs"


def test_json_logging_rotates_and_redacts_sensitive_values(tmp_path: Path) -> None:
    log_file = configure_logging(log_dir=tmp_path, max_bytes=180, backup_count=1)
    logger = logging.getLogger("observability-test")
    log_event(
        logger, logging.INFO, "crawler_failed", source="fixture",
        authorization="Bearer very-secret-token", url="https://example.test/a?token=leak",
    )
    for _ in range(8):
        log_event(logger, logging.INFO, "crawler_finished", status="success", error="x" * 80)
    log_event(logger, logging.INFO, "privacy_check", authorization="Bearer very-secret-token")
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("app.log*"))
    assert log_file.exists()
    assert (tmp_path / "app.log.1").exists()
    assert "very-secret-token" not in text and "token=leak" not in text
    assert "crawler_finished" in text
    assert json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])["event"] == "privacy_check"


def test_diagnostics_shape_and_stale_source_error_is_cleared() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    source = Source(code="fixture", name="Fixture", base_url="https://fixture.test", last_error="timeout")
    session.add(source)
    session.commit()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/runtime/diagnostics")
        assert response.status_code == 200
        payload = response.json()
        assert {"runtime", "database", "crawler", "scheduler", "sources"} <= payload.keys()
        assert payload["latest_error_summary"]["code"] == "fixture"
        source.last_error = None
        session.commit()
        recovered = TestClient(app).get("/api/runtime/diagnostics").json()
        assert recovered["latest_error_summary"] is None
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()
