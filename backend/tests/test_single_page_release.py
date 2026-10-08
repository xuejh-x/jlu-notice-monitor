from datetime import UTC, date, datetime
from pathlib import Path
import asyncio
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import api_router
import app.api.routes as routes
import app.api.source_management as management
from app.crawler.runner import CrawlerManager
from app.database import Base, get_db
from app.models import Notice, NoticeSourceRelation, Source, UserState


@pytest.fixture
def isolated_api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    application = FastAPI()
    application.include_router(api_router)

    def database():
        with Session(engine) as session:
            yield session

    application.dependency_overrides[get_db] = database
    with Session(engine) as db:
        ordinary = Source(code="ordinary", name="Ordinary", base_url="https://example.test/",
                          ownership="CUSTOM_LOCAL_PUBLIC", execution_policy="local_only")
        monitor = Source(code="page-monitor", name="Monitor", base_url="https://example.test/page",
                         ownership="CUSTOM_LOCAL_PUBLIC", execution_policy="local_only",
                         source_type="single_page_monitor", enabled=True)
        db.add_all([ordinary, monitor]); db.commit()
        ids = ordinary.id, monitor.id
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client, engine, ids
    engine.dispose()


def add_notice(db, source_id, title, published, detected):
    notice = Notice(title=title, normalized_title=title, source_id=source_id,
                    url=f"https://example.test/{title}", canonical_url=f"https://example.test/{title}",
                    content_hash=title, publish_date=published, first_seen_at=detected)
    db.add(notice); db.flush()
    db.add_all([UserState(notice_id=notice.id, is_read=False),
                NoticeSourceRelation(notice_id=notice.id, source_id=source_id,
                                     source_url=notice.url, content_hash=title)])


def test_mixed_latest_pagination_and_dashboard_keep_publication_semantics(isolated_api):
    client, engine, (ordinary, monitor) = isolated_api
    with Session(engine) as db:
        add_notice(db, ordinary, "old", date(2024, 1, 1), datetime(2030, 1, 1))
        add_notice(db, ordinary, "dated", date(2026, 10, 8), datetime(2026, 10, 7))
        add_notice(db, ordinary, "unknown", None, datetime(2031, 1, 1))
        add_notice(db, monitor, "latest", None, datetime(2026, 10, 7, 16, 30))
        add_notice(db, monitor, "earlier", None, datetime(2026, 10, 7, 15))
        db.commit()
    expected = ["latest", "dated", "earlier", "old", "unknown"]
    pages = [client.get("/api/notices", params={"read": "false", "page_size": 2, "page": p}).json()
             for p in (1, 2, 3)]
    assert [n["title"] for page in pages for n in page["items"]] == expected
    assert all(page["total"] == 5 and page["total_pages"] == 3 for page in pages)
    assert pages[0]["items"][0]["publish_date"] is None
    assert datetime.fromisoformat(pages[0]["items"][0]["first_seen_at"]) == datetime(2026, 10, 7, 16, 30, tzinfo=UTC)
    assert pages[0]["items"][1]["first_seen_at"] == "2026-10-07T00:00:00"
    recent = client.get("/api/dashboard").json()["recent_notices"]
    assert [n["title"] for n in recent] == expected
    ordinary_list = client.get("/api/notices?source=ordinary").json()["items"]
    assert [n["title"] for n in ordinary_list] == ["dated", "old", "unknown"]


@pytest.mark.parametrize("params,expected", [
    ({"date_from": "2026-10-08", "date_to": "2026-10-08"}, ["last", "start", "dated"]),
    ({"date_from": "2026-10-08"}, ["next", "last", "start", "dated"]),
    ({"date_to": "2026-10-07"}, ["before", "old"]),
])
def test_date_boundaries_use_local_detection_day_only_for_monitors(isolated_api, params, expected):
    client, engine, (ordinary, monitor) = isolated_api
    with Session(engine) as db:
        for title, detected in [
            ("before", datetime(2026, 10, 7, 15, 59, 59, 999999)),
            ("start", datetime(2026, 10, 7, 16)),
            ("last", datetime(2026, 10, 8, 15, 59, 59, 999999)),
            ("next", datetime(2026, 10, 8, 16)),
        ]:
            add_notice(db, monitor, title, None, detected)
        add_notice(db, ordinary, "dated", date(2026, 10, 8), datetime(2020, 1, 1))
        add_notice(db, ordinary, "old", date(2026, 10, 7), datetime(2030, 1, 1))
        add_notice(db, ordinary, "unknown", None, datetime(2026, 10, 8))
        db.commit()
    result = client.get("/api/notices", params=params).json()
    assert [n["title"] for n in result["items"]] == expected
    assert result["total"] == len(expected)


def test_monitor_type_not_code_controls_effective_time(isolated_api):
    client, engine, (_, monitor) = isolated_api
    with Session(engine) as db:
        add_notice(db, monitor, "detected", date(2020, 1, 1), datetime(2026, 10, 8))
        db.commit()
    response = client.get("/api/notices?date_from=2026-10-08&source=page-monitor").json()
    assert response["total"] == 1
    assert response["items"][0]["publish_date"] == "2020-01-01"


def test_detection_date_range_handles_dst_without_fixed_24_hour_window(isolated_api, monkeypatch):
    client, engine, (_, monitor) = isolated_api
    monkeypatch.setattr(routes, "load_yaml", lambda _: {"app": {"timezone": "America/New_York"}}, raising=False)
    with Session(engine) as db:
        for title, detected in [("before", datetime(2026, 3, 8, 4, 59, 59)),
                                ("start", datetime(2026, 3, 8, 5)),
                                ("last", datetime(2026, 3, 9, 3, 59, 59)),
                                ("next", datetime(2026, 3, 9, 4))]:
            add_notice(db, monitor, title, None, detected)
        db.commit()
    data = client.get("/api/notices?date_from=2026-03-08&date_to=2026-03-08").json()
    assert [n["title"] for n in data["items"]] == ["last", "start"]


def test_postgres_time_ordering_compiles_without_sqlite_function():
    from sqlalchemy import create_mock_engine, select
    from sqlalchemy.dialects import postgresql

    engine = create_mock_engine("postgresql://", lambda *args, **kwargs: None)
    with Session(engine) as db:
        sql = str(select(Notice.id).order_by(*routes._latest_notice_ordering(db))
                  .compile(dialect=postgresql.dialect()))
    assert "CASE WHEN" in sql and "notices.first_seen_at" in sql
    assert "timezone(" in sql and "TIMESTAMP WITHOUT TIME ZONE" in sql
    assert "jlu_publication_midnight_utc" not in sql


def test_default_zone_works_when_windows_has_no_iana_database(monkeypatch):
    from zoneinfo import ZoneInfoNotFoundError

    def unavailable(_):
        raise ZoneInfoNotFoundError("not bundled")

    monkeypatch.setattr(routes, "ZoneInfo", unavailable)
    _, zone = routes._notice_timezone()
    assert routes._date_start_utc(date(2026, 10, 8), zone) == datetime(2026, 10, 7, 16)


def test_source_check_http_starts_on_event_loop_and_rejects_overlap(isolated_api, monkeypatch, tmp_path: Path):
    client, _, (_, monitor) = isolated_api
    manager = CrawlerManager(cache_dir=tmp_path)
    release = threading.Event()
    entered = threading.Event()

    async def controlled_run(**kwargs):
        assert kwargs["source_code"] == "page-monitor"
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)

    monkeypatch.setattr(manager, "run", controlled_run)
    monkeypatch.setattr(management, "crawler_manager", manager)
    try:
        response = client.post(f"/api/source-config/{monitor}/check")
        assert response.status_code == 202, response.text
        assert response.json() == {"status": "started", "source": "page-monitor"}
        assert entered.wait(1)
        assert client.post(f"/api/source-config/{monitor}/check").status_code == 409
    finally:
        release.set()


@pytest.mark.parametrize("scenario,expected", [("missing", 404), ("disabled", 409),
                                               ("reauth", 409), ("startup_error", 500)])
def test_source_check_http_errors_do_not_claim_started(isolated_api, monkeypatch, scenario, expected):
    client, engine, (_, monitor) = isolated_api
    calls = []

    class Manager:
        def start(self, *args, **kwargs):
            calls.append(args)
            raise RuntimeError("simulated task initialization failure")

    monkeypatch.setattr(management, "crawler_manager", Manager())
    with Session(engine) as db:
        source = db.get(Source, monitor)
        if scenario == "disabled": source.enabled = False
        if scenario == "reauth": source.health_state = "needs_reauth"
        db.commit()
    target = monitor + 100 if scenario == "missing" else monitor
    response = client.post(f"/api/source-config/{target}/check")
    assert response.status_code == expected
    assert (len(calls) == 1) == (scenario == "startup_error")
