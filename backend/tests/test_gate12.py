from __future__ import annotations

import asyncio
from datetime import date, datetime
import os
import sqlite3

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.public_feed import public_notices
from app.api.source_management import (
    DeleteRequest,
    EnableRequest,
    SourceCreate,
    SourceDraft,
    SourceEdit,
    _issue_preview_token,
    create_source,
    delete_source,
    edit_source,
    preview_source,
    update_enabled,
)
from app.crawler.runner import CrawlerAlreadyRunning
from app.crawler.runner import CrawlerManager
from app.crawler.startup import StartupSyncCoordinator
from app.database import Base, get_db
from app.database.migrations import run_gate12_migrations
from app.main import app
from app.models import ImportanceRule, Notice, NoticeSourceRelation, Source, UserState
from app.services.importance import ensure_importance_rules, rescore_all_notices, restore_default_rules
from app.services.source_security import UnsafeSourceUrl, validate_source_url, validate_url_syntax
from app.services.credentials import CredentialStore
from app.paths import get_auth_profile_dir
from app.sources.cloud import CloudFeedSource
from app.sources.base import SourceError
from app.sources.generic import SafeFetcher, parse_configured_html, parse_rss_atom


class FakeCrawler:
    def __init__(self, *, collision: bool = False, failure: bool = False) -> None:
        self.starts: list[str] = []
        self.collision = collision
        self.failure = failure

    def start(self, *, trigger: str):
        self.starts.append(trigger)
        if self.collision:
            raise CrawlerAlreadyRunning("already running")
        if self.failure:
            raise RuntimeError("fixture start failure")
        loop = asyncio.get_event_loop_policy().get_event_loop()
        result = type("Result", (), {"status": "success"})()
        return loop.create_task(asyncio.sleep(0, result=result))


def make_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


@pytest.mark.asyncio
async def test_startup_sync_triggers_exactly_once_and_records_completion() -> None:
    crawler = FakeCrawler()
    coordinator = StartupSyncCoordinator(crawler)  # type: ignore[arg-type]
    assert coordinator.trigger_once() is True
    assert coordinator.trigger_once() is False
    assert crawler.starts == ["startup"]
    assert coordinator.status()["outcome"] == "started"
    assert coordinator.status()["started_at"] is not None
    assert coordinator.status()["completed_at"] is None
    await asyncio.sleep(0.01)
    assert coordinator.status()["outcome"] == "success"
    assert coordinator.status()["completed_at"] is not None

    busy = FakeCrawler(collision=True)
    skipped = StartupSyncCoordinator(busy)  # type: ignore[arg-type]
    assert skipped.trigger_once() is True
    assert skipped.status()["outcome"] == "skipped_running"
    assert skipped.status()["skipped_reason"] == "crawler_already_running"
    assert skipped.status()["completed_at"] is not None
    assert skipped.trigger_once() is False


def test_startup_sync_start_failure_is_isolated() -> None:
    coordinator = StartupSyncCoordinator(FakeCrawler(failure=True))  # type: ignore[arg-type]
    assert coordinator.trigger_once() is True
    assert coordinator.status()["outcome"] == "failure"
    assert coordinator.status()["completed_at"] is not None


def test_gate12_additive_migration_preserves_old_rows(tmp_path) -> None:
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sources (
          id INTEGER PRIMARY KEY, code VARCHAR(40) UNIQUE, name VARCHAR(200),
          base_url VARCHAR(500), enabled BOOLEAN, last_checked_at DATETIME,
          last_success_at DATETIME, last_error TEXT, consecutive_errors INTEGER
        );
        CREATE TABLE notices (id INTEGER PRIMARY KEY, title VARCHAR(1000));
        CREATE TABLE user_states (
          id INTEGER PRIMARY KEY, notice_id INTEGER UNIQUE, is_read BOOLEAN,
          is_archived BOOLEAN, is_favorite BOOLEAN, updated_at DATETIME
        );
        CREATE TABLE favorites (id INTEGER PRIMARY KEY, notice_id INTEGER UNIQUE, created_at DATETIME);
        CREATE TABLE schema_migrations (version VARCHAR(40) PRIMARY KEY, applied_at DATETIME);
        INSERT INTO sources VALUES (7, 'cse', '学院', 'https://example.edu', 1, NULL, NULL, NULL, 0);
        INSERT INTO notices VALUES (11, '保留通知');
        INSERT INTO user_states VALUES (5, 11, 1, 0, 1, '2026-09-01 10:00:00');
        INSERT INTO favorites VALUES (3, 11, '2026-09-01 10:00:00');
        """
    )
    connection.commit()
    connection.close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    run_gate12_migrations(engine)
    run_gate12_migrations(engine)
    with engine.connect() as db:
        source = db.exec_driver_sql(
            "SELECT id, code, ownership, subscribed FROM sources WHERE id = 7"
        ).one()
        notice = db.exec_driver_sql("SELECT id, title, public_id FROM notices WHERE id = 11").one()
        user_state = db.exec_driver_sql("SELECT is_read, is_favorite FROM user_states WHERE notice_id = 11").one()
        favorite = db.exec_driver_sql("SELECT notice_id FROM favorites WHERE notice_id = 11").one()
        assert tuple(source) == (7, "cse", "OFFICIAL_CLOUD", 1)
        assert tuple(notice) == (11, "保留通知", None)
        assert tuple(user_state) == (1, 1)
        assert favorite.notice_id == 11


def test_rss_atom_and_advanced_html_parsing() -> None:
    rss = """<?xml version='1.0'?><rss><channel><item><title>报名通知</title>
    <link>https://example.edu/a</link><pubDate>Tue, 02 Sep 2025 10:00:00 GMT</pubDate>
    <description><![CDATA[<p>正文</p>]]></description></item></channel></rss>"""
    parsed = parse_rss_atom(rss, "https://example.edu/feed")
    assert parsed[0].title == "报名通知"
    assert parsed[0].publish_date == date(2025, 9, 2)
    html = """<ul class='items'><li><a class='title' href='/1'>第一条</a><time>2025-09-01</time></li></ul>"""
    configured = parse_configured_html(
        html,
        "https://example.edu/notices",
        {"item_selector": ".items li", "title_selector": ".title", "link_selector": ".title", "date_selector": "time"},
    )
    assert configured[0].url == "https://example.edu/1"
    assert configured[0].publish_date == date(2025, 9, 1)
    with pytest.raises(SourceError, match="did not find"):
        parse_configured_html(html, "https://example.edu", {"item_selector": ".missing"})


@pytest.mark.asyncio
async def test_source_url_security_and_response_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    assert validate_url_syntax("https://example.edu/notices")
    with pytest.raises(UnsafeSourceUrl):
        validate_url_syntax("file:///etc/passwd")
    with pytest.raises(UnsafeSourceUrl):
        await validate_source_url("http://127.0.0.1/private")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": "99999999"}, content=b"small")

    fetcher = SafeFetcher(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "app.sources.generic.validate_source_url",
        lambda *args, **kwargs: asyncio.sleep(0, result=args[0]),
    )
    fetcher.retries = 0
    with pytest.raises(SourceError, match="size limit"):
        await fetcher.get("https://example.edu")
    await fetcher.close()


def test_public_feed_contains_facts_but_no_personal_state_or_score() -> None:
    db = make_session()
    source = Source(code="official", name="官方", base_url="https://example.edu", ownership="OFFICIAL_CLOUD")
    db.add(source)
    db.flush()
    notice = Notice(
        title="通知", normalized_title="通知", url="https://example.edu/1",
        canonical_url="https://example.edu/1", source_id=source.id, content="正文",
        content_hash="a" * 64, category="research", importance_score=99,
        first_seen_at=datetime(2025, 1, 1), last_seen_at=datetime(2025, 1, 1), updated_at=datetime(2025, 1, 1),
    )
    db.add(notice)
    db.flush()
    db.add_all([
        NoticeSourceRelation(notice_id=notice.id, source_id=source.id, source_url=notice.url, content_hash=notice.content_hash),
        UserState(notice_id=notice.id, is_read=True, is_favorite=True),
    ])
    db.commit()
    payload = public_notices(source=None, updated_after=None, after_id=0, page_size=100, db=db)
    item = payload["items"][0]
    assert item["title"] == "通知"
    assert "importance_score" not in item
    assert "is_read" not in item and "is_favorite" not in item
    assert len(item["public_id"]) == 64
    db.close()


def test_importance_rules_rescore_existing_notices_without_touching_user_state() -> None:
    db = make_session()
    source = Source(code="local", name="本地", base_url="https://example.edu", ownership="CUSTOM_LOCAL_PUBLIC")
    db.add(source)
    db.flush()
    notice = Notice(
        title="PWN 实验室招募", normalized_title="pwn实验室招募", url="https://example.edu/1",
        canonical_url="https://example.edu/1", source_id=source.id, content="Linux",
        content_hash="b" * 64, category="research", importance_score=0,
    )
    db.add(notice)
    db.flush()
    state = UserState(notice_id=notice.id, is_read=True, is_favorite=True)
    db.add(state)
    db.commit()
    ensure_importance_rules(db)
    pwn = db.scalar(select(ImportanceRule).where(ImportanceRule.keyword == "PWN"))
    assert pwn is not None
    pwn.weight = -20
    db.commit()
    rescore_all_notices(db)
    low_score = notice.importance_score
    pwn.weight = 35
    db.commit()
    rescore_all_notices(db)
    assert notice.importance_score > low_score
    db.refresh(state)
    assert state.is_read and state.is_favorite
    assert restore_default_rules(db) == 1
    db.close()


def test_private_source_creation_never_serializes_password() -> None:
    db = make_session()
    draft = SourceDraft(
        name="内部通知", list_url="https://internal.example.edu/notices", kind="private",
        parser="generic_html", auth_type="browser_session", login_url="https://internal.example.edu/login",
        username="student", password="do-not-return", remember_credentials=False,
    )
    payload = SourceCreate(**draft.model_dump(), preview_token=_issue_preview_token(draft))
    response = create_source(payload, db)
    assert response["health_state"] == "needs_reauth"
    assert response["password_saved"] is False
    assert "password" not in response and "credential_ref" not in response
    db.close()


def test_custom_public_crud_and_private_scheduler_pause() -> None:
    db = make_session()
    draft = SourceDraft(name="实验室", list_url="https://lab.example.edu/notices", parser="rss")
    created = create_source(
        SourceCreate(**draft.model_dump(), preview_token=_issue_preview_token(draft)), db
    )
    source = db.get(Source, created["id"]); assert source is not None and source.enabled
    renamed = edit_source(source.id, SourceEdit(name="实验室通知"), db)
    assert renamed["name"] == "实验室通知"
    assert delete_source(source.id, DeleteRequest(clear_local_login=False), db)["deleted"]
    assert source.is_deleted and not source.enabled

    private = Source(
        code="private-a", name="内部", base_url="https://private.example.edu",
        ownership="CUSTOM_LOCAL_PRIVATE", auth_type="browser_session", parser="generic_html",
        enabled=False, health_state="needs_reauth",
    )
    db.add(private); db.commit()
    with pytest.raises(Exception) as error:
        update_enabled(private.id, EnableRequest(enabled=True), db)
    assert getattr(error.value, "status_code", None) == 409
    response = update_enabled(
        private.id,
        EnableRequest(enabled=True, authentication_warning_acknowledged=True),
        db,
    )
    assert response["health_state"] == "needs_reauth"
    configs = CrawlerManager._load_source_configs(db)
    private_config = next(item for item in configs if item["code"] == "private-a")
    assert private_config["enabled"] is False
    db.close()


@pytest.mark.asyncio
async def test_failed_preview_does_not_persist_source(monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_session()
    draft = SourceDraft(name="不支持页面", list_url="https://unsupported.example.edu/notices")

    async def allow_test_url(url: str, **_: object) -> str:
        return url

    async def fail_parse(_: object) -> list[object]:
        raise SourceError("unsupported structure")

    monkeypatch.setattr("app.api.source_management.validate_local_source_url", allow_test_url)
    monkeypatch.setattr("app.sources.generic.GenericPublicSource.fetch_list", fail_parse)
    with pytest.raises(HTTPException) as error:
        await preview_source(draft)
    assert error.value.status_code == 422
    assert db.scalars(select(Source)).all() == []
    with pytest.raises(HTTPException) as create_error:
        create_source(SourceCreate(**draft.model_dump(), preview_token="not-issued"), db)
    assert create_error.value.status_code == 409
    assert db.scalars(select(Source)).all() == []
    db.close()


def test_private_session_health_controls_scheduled_reuse_without_reprompt() -> None:
    db = make_session()
    valid = Source(
        code="private-valid",
        name="有效会话",
        base_url="https://private.example.edu/notices",
        ownership="CUSTOM_LOCAL_PRIVATE",
        parser="generic_html",
        auth_type="cookie",
        credential_ref="source-private-valid",
        enabled=True,
        health_state="authenticated",
    )
    expired = Source(
        code="private-expired",
        name="过期会话",
        base_url="https://private.example.edu/expired",
        ownership="CUSTOM_LOCAL_PRIVATE",
        parser="generic_html",
        auth_type="browser_session",
        enabled=True,
        health_state="needs_reauth",
    )
    disabled = Source(
        code="private-disabled",
        name="停用会话",
        base_url="https://private.example.edu/disabled",
        ownership="CUSTOM_LOCAL_PRIVATE",
        parser="generic_html",
        auth_type="browser_session",
        enabled=False,
        health_state="disabled",
    )
    db.add_all([valid, expired, disabled])
    db.commit()

    configs = {item["code"]: item for item in CrawlerManager._load_source_configs(db)}
    assert configs["private-valid"]["enabled"] is True
    assert configs["private-valid"]["parser"] == "authenticated_http"
    assert configs["private-expired"]["enabled"] is False
    assert configs["private-disabled"]["enabled"] is False
    assert expired.reauth_notified_at is None
    db.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI validation")
def test_dpapi_store_does_not_write_plaintext_and_profiles_are_per_source(tmp_path) -> None:
    store = CredentialStore(tmp_path / "credentials")
    store.save("source-local-a", "very-secret-password")
    encrypted = (tmp_path / "credentials" / "source-local-a.dpapi").read_bytes()
    assert b"very-secret-password" not in encrypted
    assert store.load("source-local-a") == "very-secret-password"
    first = get_auth_profile_dir("local-a", "test", tmp_path)
    second = get_auth_profile_dir("local-b", "test", tmp_path)
    assert first != second and first.parent == second.parent


@pytest.mark.asyncio
async def test_cloud_feed_import_is_incremental_and_failure_keeps_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_session()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr("app.sources.cloud.SessionLocal", factory)
    source = Source(code="official", name="官方", base_url="https://official.test", ownership="OFFICIAL_CLOUD", parser="cloud_feed")
    db.add(source); db.commit()
    payload = {
        "version": "1", "has_more": False,
        "items": [{
            "public_id": "p" * 64, "title": "云端通知", "url": "https://official.test/1",
            "publish_date": "2026-09-01", "publisher": "学院", "content": "PWN 报名",
            "category": "cybersecurity_competition", "registration_deadline": "2026-09-10",
            "attachments": [],
        }],
        "next": {"updated_after": "2026-09-02T00:00:00", "after_id": 8},
    }
    adapter = CloudFeedSource({"code": "official", "name": "官方", "base_url": "https://official.test", "public_feed_url": "https://cloud.test/api/public/v1"})
    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    candidates = await adapter.fetch_list()
    assert len(candidates) == 1 and candidates[0].public_id == "p" * 64
    assert CrawlerManager._persist_candidate(db, source, candidates[0], False) == "NEW"
    notice = db.scalar(select(Notice).where(Notice.public_id == "p" * 64)); assert notice is not None
    state = db.scalar(select(UserState).where(UserState.notice_id == notice.id)); assert state is not None
    state.is_read = True; state.is_favorite = True; db.commit()
    cached_count = len(db.scalars(select(Notice)).all())

    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    with pytest.raises(SourceError, match="PUBLIC_FEED_UNAVAILABLE"):
        await adapter.fetch_list()
    assert len(db.scalars(select(Notice)).all()) == cached_count
    db.refresh(state); assert state.is_read and state.is_favorite
    await adapter.close(); db.close()


def test_official_subscription_hides_cached_notice_but_preserves_it() -> None:
    db = make_session()
    source = Source(code="official", name="官方", base_url="https://example.edu", ownership="OFFICIAL_CLOUD", subscribed=False)
    db.add(source)
    db.flush()
    notice = Notice(title="缓存通知", normalized_title="缓存通知", url="https://example.edu/1", canonical_url="https://example.edu/1", source_id=source.id, content="", content_hash="c" * 64, category="other", importance_score=20)
    db.add(notice)
    db.flush()
    db.add(NoticeSourceRelation(notice_id=notice.id, source_id=source.id, source_url=notice.url, content_hash=notice.content_hash))
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/notices")
        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert db.get(Notice, notice.id) is not None
    finally:
        app.dependency_overrides.clear()
        db.close()
