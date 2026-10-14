from __future__ import annotations

import json
import logging
from pathlib import Path
import ssl

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
from app.config import Settings
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.logging_config import JsonFormatter
from app.models import Favorite, Notice, NoticeSourceRelation, Source, UserState
from app.services.http_diagnostics import exception_summary
from app.sources.base import SourceError, StaticHTMLSource
from app.sources.oa_public import OAPublicSource, OAAttachmentReference


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture(autouse=True)
def enable_source_loggers(monkeypatch: pytest.MonkeyPatch) -> None:
    # Other runtime tests load Uvicorn's logging config, which disables existing
    # application loggers globally. Keep these assertions independent of order.
    for name in ("app.sources.base", "app.crawler.runner"):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)


def config() -> dict:
    return {
        "code": "oa", "name": "OA", "base_url": "https://oa.test",
        "parser": "oa_public", "sections": [{"url": "https://oa.test/list"}],
    }


def eof_error(request: httpx.Request) -> httpx.ConnectError:
    cause = ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING")
    error = httpx.ConnectError("", request=request)
    error.__cause__ = cause
    return error


def test_summary_preserves_empty_wrapper_cause_and_stops_cycles() -> None:
    error = eof_error(httpx.Request("GET", "https://oa.test/list"))
    error.__cause__.__context__ = error
    summary = exception_summary(error)
    assert "ConnectError('')" in summary
    assert "SSLEOFError" in summary and "UNEXPECTED_EOF_WHILE_READING" in summary
    assert summary.count("ConnectError") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["eof", "timeout", "http_status"])
async def test_get_failure_is_actionable_and_json_logs_keep_diagnostics(
    failure: str, caplog: pytest.LogCaptureFixture,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if failure == "eof":
            raise eof_error(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("", request=request)
        return httpx.Response(503, text="unavailable")

    adapter = StaticHTMLSource(config())
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(respond), timeout=0.1)
    adapter.retries = 1
    adapter.backoff = 0
    caplog.set_level(logging.INFO)
    try:
        with pytest.raises(SourceError) as caught:
            await adapter._get("https://oa.test/list?token=private")
        assert caught.value.__cause__ is not None
        expected = {"eof": "SSLEOFError", "timeout": "ReadTimeout", "http_status": "503"}[failure]
        assert expected in str(caught.value)
        events = [json.loads(JsonFormatter().format(r)) for r in caplog.records
                  if getattr(r, "event", "") == "source_http_request_failed"]
        assert [e["attempt"] for e in events] == [1, 2]
        assert events[-1]["url"] == "https://oa.test/list"
        assert events[-1]["max_attempts"] == 2
        assert events[-1]["timeout_seconds"]["read"] == 0.1
        assert events[-1]["duration_seconds"] >= 0
        assert expected in events[-1]["error"]
        assert "token=private" not in json.dumps(events)
        assert events[-1].get("http_status") == (503 if failure == "http_status" else None)
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_attachment_post_preserves_eof_cause(caplog: pytest.LogCaptureFixture) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise eof_error(request)

    adapter = OAPublicSource(config())
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    adapter.retries = 0
    caplog.set_level(logging.INFO)
    try:
        with pytest.raises(SourceError, match="SSLEOFError") as caught:
            await adapter._attachment_url(OAAttachmentReference("a.pdf", "a.pdf", "123"), "https://oa.test/123")
        assert isinstance(caught.value.__cause__, httpx.ConnectError)
        record = next(r for r in caplog.records if getattr(r, "event", "") == "source_http_request_failed")
        assert json.loads(JsonFormatter().format(record))["method"] == "POST"
    finally:
        await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("is_read", [True, False])
async def test_cloud_failure_really_fetches_local_and_preserves_existing_state(
    is_read: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixtures = Path(__file__).parent / "fixtures"
    calls: list[str] = []
    failing = False

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.method + " " + request.url.path)
        if failing:
            raise eof_error(request)
        if request.method == "POST":
            return httpx.Response(200, text="encoded-attachment")
        filename = "oa_list.html" if request.url.path == "/list" else "oa_detail.html"
        return httpx.Response(200, text=(fixtures / filename).read_text(encoding="utf-8"))

    real_build = runner_module.build_source
    def build(source_config: dict):
        adapter = real_build(source_config)
        # The cloud constructor fails as in the installed app (no feed URL).
        # Local uses the real OA adapter/parser, with isolated HTTP responses.
        adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        adapter.retries = 0
        return adapter

    settings = Settings(_env_file=None, environment="test", deployment_role="desktop",
                        public_feed_url=None, app_data_dir=str(tmp_path))
    monkeypatch.setattr(runner_module, "get_settings", lambda: settings)
    monkeypatch.setattr("app.sources.cloud.get_settings", lambda: settings)
    monkeypatch.setattr(runner_module, "build_source", build)
    caplog.set_level(logging.INFO)
    with make_session() as db:
        source = Source(code="oa", name="OA", base_url="https://oa.test")
        db.add(source)
        db.commit()
        source_id = source.id
        monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
        run_config = {**config(), "parser": "cloud_feed", "fallback_parser": "oa_public",
                      "ownership": "OFFICIAL_CLOUD", "execution_policy": "cloud_preferred",
                      "effective_execution": "cloud"}
        manager = CrawlerManager(tmp_path)
        first = await manager._run_source(run_config, False)
        assert first.status == "success" and calls
        notice = db.scalar(select(Notice))
        notice_id = notice.id
        state = db.scalar(select(UserState).where(UserState.notice_id == notice_id))
        state.is_read = is_read
        db.add(Favorite(notice_id=notice_id))
        db.commit()
        ids = db.scalars(select(Notice.id).order_by(Notice.id)).all()
        relations = db.scalars(select(NoticeSourceRelation.id).order_by(NoticeSourceRelation.id)).all()
        last_success = db.get(Source, source_id).last_success_at
        failing = True
        failed = await manager._run_source(run_config, False)
        assert [a.status for a in failed.attempts] == ["failure", "failure"]
        assert "SSLEOFError" in failed.attempts[-1].error
        assert failed.list_duration_seconds >= 0
        assert db.get(Source, source_id).last_success_at == last_success
        failing = False
        for _ in range(2):
            result = await manager._run_source(run_config, False)
            assert [(a.execution, a.status) for a in result.attempts] == [("cloud", "failure"), ("local", "success")]
            assert result.new_count == 0
        assert db.scalars(select(Notice.id).order_by(Notice.id)).all() == ids
        assert db.scalars(select(NoticeSourceRelation.id).order_by(NoticeSourceRelation.id)).all() == relations
        assert db.scalar(select(UserState).where(UserState.notice_id == notice_id)).is_read == is_read
        assert db.scalar(select(Favorite.notice_id)) == notice_id
        assert db.get(Source, source_id).last_error is None
        events = [json.loads(JsonFormatter().format(r)) for r in caplog.records
                  if getattr(r, "event", "") == "source_attempt_finished"]
        assert any(e["effective_execution"] == "cloud" and "PUBLIC_FEED_NOT_CONFIGURED" in e["error"] for e in events)
        assert any(e["effective_execution"] == "local" and e["status"] == "success" for e in events)
        finished = [json.loads(JsonFormatter().format(r)) for r in caplog.records
                    if getattr(r, "event", "") == "source_finished"][-1]
        assert finished["fallback_reason"] == "PUBLIC_FEED_NOT_CONFIGURED"
        assert finished["effective_execution"] == "local"
