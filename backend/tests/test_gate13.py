from __future__ import annotations

import asyncio
from datetime import datetime
import sqlite3
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import cloud_admin
from app.api.cloud_admin import CloudSourceDraft
from app.api.public_feed import public_sources
from app.api.source_management import CloudSourceCreateRequest, PromotionRequest, create_cloud_source, promote_source
from app.crawler.runner import CrawlerManager
from app.database import Base, get_db
from app.database.migrations import run_gate12_migrations, run_gate13_migrations
from app.main import app
from app.models import Notice, NoticeSourceRelation, Source, UserState
from app.schemas.notice import NoticeCandidate
from app.services.source_identity import canonicalize_source_url, resolve_cloud_execution, source_identity
from app.services.source_security import UnsafeSourceUrl, validate_source_url
from app.sources.base import LoginExpiredError, SourceError
from app.sources.generic import GenericPublicSource, SafeFetcher


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def admin_settings(key: str | None = "MOCK-FIXTURE-ADMIN") -> SimpleNamespace:
    return SimpleNamespace(admin_key=key, admin_auth_attempts_per_minute=10)


def test_source_identity_normalizes_transport_noise_but_keeps_meaningful_query() -> None:
    left = "HTTPS://Example.COM:443/notices/?b=2&utm_source=x&a=1#fragment"
    right = "https://example.com/notices?a=1&b=2"
    assert canonicalize_source_url(left) == right
    assert source_identity(left) == source_identity(right)
    assert source_identity(right) != source_identity("https://example.com/notices?a=2&b=2")


def test_cloud_policy_manual_overrides_win() -> None:
    assert resolve_cloud_execution(execution="cloud", cloud_policy="force_enabled", enabled=False)
    assert not resolve_cloud_execution(execution="cloud", cloud_policy="force_disabled", enabled=True)
    assert resolve_cloud_execution(execution="cloud", cloud_policy="auto", enabled=True)
    assert not resolve_cloud_execution(execution="cloud", cloud_policy="auto", enabled=False)
    assert not resolve_cloud_execution(execution="local", cloud_policy="force_enabled", enabled=True)


def test_gate12_to_gate13_migration_is_additive_and_preserves_personal_state(tmp_path) -> None:
    path = tmp_path / "gate12.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sources (
          id INTEGER PRIMARY KEY, code VARCHAR(40) UNIQUE, name VARCHAR(200), base_url VARCHAR(500),
          enabled BOOLEAN, last_checked_at DATETIME, last_success_at DATETIME, last_error TEXT,
          consecutive_errors INTEGER
        );
        CREATE TABLE notices (id INTEGER PRIMARY KEY, title VARCHAR(1000));
        CREATE TABLE user_states (
          id INTEGER PRIMARY KEY, notice_id INTEGER UNIQUE, is_read BOOLEAN,
          is_archived BOOLEAN, is_favorite BOOLEAN, updated_at DATETIME
        );
        CREATE TABLE schema_migrations (version VARCHAR(40) PRIMARY KEY, applied_at DATETIME);
        INSERT INTO sources VALUES (1, 'local-fixture', 'MOCK / FIXTURE', 'https://example.test/feed/', 1, NULL, NULL, NULL, 0);
        INSERT INTO notices VALUES (8, '保留通知');
        INSERT INTO user_states VALUES (4, 8, 1, 0, 1, '2026-09-02 01:00:00');
        """
    )
    connection.commit()
    connection.close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    run_gate12_migrations(engine)
    assert "source_identity" not in {item["name"] for item in inspect(engine).get_columns("sources")}
    run_gate13_migrations(engine)
    run_gate13_migrations(engine)
    with engine.connect() as db:
        source_row = db.exec_driver_sql(
            "SELECT source_identity, source_scope, execution, cloud_policy, validation_status FROM sources WHERE id=1"
        ).one()
        state = db.exec_driver_sql(
            "SELECT is_read, is_favorite FROM user_states WHERE notice_id=8"
        ).one()
        versions = {row[0] for row in db.exec_driver_sql("SELECT version FROM schema_migrations")}
    assert len(source_row.source_identity) == 64
    assert tuple(source_row[1:]) == ("official", "cloud", "auto", "passed")
    assert tuple(state) == (1, 1)
    assert versions == {"12.0", "13.0"}


def test_admin_auth_missing_invalid_valid_and_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cloud_admin, "get_settings", lambda: admin_settings())
    compared: list[tuple[bytes, bytes]] = []

    def compare(left: bytes, right: bytes) -> bool:
        compared.append((left, right))
        return left == right

    monkeypatch.setattr(cloud_admin.hmac, "compare_digest", compare)
    client = TestClient(app)
    payload = {"name": "MOCK / FIXTURE", "list_url": "https://example.test/feed"}
    assert client.post("/api/admin/sources/promote", json=payload).status_code == 401
    assert client.post(
        "/api/admin/sources/promote",
        json=payload,
        headers={"X-Notice-Hub-Admin-Key": "wrong"},
    ).status_code == 403
    assert compared == [(b"wrong", b"MOCK-FIXTURE-ADMIN")]


def test_admin_unconfigured_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cloud_admin, "get_settings", lambda: admin_settings(None))
    response = TestClient(app).post(
        "/api/admin/sources/promote",
        json={"name": "MOCK / FIXTURE", "list_url": "https://example.test/feed"},
        headers={"X-Notice-Hub-Admin-Key": "anything"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Admin cloud promotion is not configured."


def test_admin_promote_and_duplicate_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_session()
    monkeypatch.setattr(cloud_admin, "get_settings", lambda: admin_settings())

    async def fixture_preview(_: CloudSourceDraft):
        return "rss", [{"title": "MOCK / FIXTURE notice", "url": "https://example.test/1", "publish_date": None}]

    monkeypatch.setattr(cloud_admin, "_cloud_preview", fixture_preview)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        body = {"name": "MOCK / FIXTURE RSS", "list_url": "https://example.test/feed/", "parser": "rss"}
        headers = {"X-Notice-Hub-Admin-Key": "MOCK-FIXTURE-ADMIN"}
        first = client.post("/api/admin/sources/promote", json=body, headers=headers)
        second = client.post(
            "/api/admin/sources/promote",
            json={**body, "list_url": "https://EXAMPLE.test:443/feed#ignored"},
            headers=headers,
        )
        assert first.status_code == second.status_code == 200
        assert first.json()["reused"] is False and second.json()["reused"] is True
        assert first.json()["cloud_source_id"] == second.json()["cloud_source_id"]
        policy = client.patch(
            f"/api/admin/sources/{first.json()['cloud_source_id']}/cloud-policy",
            json={"cloud_policy": "force_disabled"},
            headers=headers,
        )
        assert policy.status_code == 200
        assert policy.json()["cloud_policy"] == "force_disabled"
        assert public_sources(db)["items"][0]["id"] == first.json()["cloud_source_id"]
        assert len(db.scalars(select(Source)).all()) == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_cloud_source_crud_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_session()
    monkeypatch.setattr(cloud_admin, "get_settings", lambda: admin_settings())

    async def fixture_preview(_: CloudSourceDraft):
        return "api", [{"title": "MOCK API notice", "url": "https://api.example.test/1", "publish_date": None}]

    monkeypatch.setattr(cloud_admin, "_cloud_preview", fixture_preview)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        headers = {"X-Notice-Hub-Admin-Key": "MOCK-FIXTURE-ADMIN"}
        created = client.post(
            "/api/cloud/sources",
            headers=headers,
            json={
                "name": "MOCK API",
                "list_url": "https://api.example.test/notices",
                "parser": "api",
                "category": "research",
                "crawl_interval_seconds": 1800,
                "public_shared": True,
            },
        )
        assert created.status_code == 201
        cloud_id = created.json()["cloud_source_id"]
        listed = client.get("/api/cloud/sources", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["category"] == "research"
        updated = client.patch(
            f"/api/cloud/sources/{cloud_id}",
            headers=headers,
            json={"name": "MOCK API Updated", "cloud_policy": "force_disabled"},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "MOCK API Updated"
        assert updated.json()["status"] == "disabled"
        deleted = client.delete(f"/api/cloud/sources/{cloud_id}", headers=headers)
        assert deleted.status_code == 200 and deleted.json()["deleted"] is True
        assert client.get("/api/cloud/sources", headers=headers).json()["items"] == []
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.asyncio
async def test_desktop_direct_cloud_create_maps_registry_and_disables_local_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_session()
    monkeypatch.setattr("app.api.source_management._validate_preview_token", lambda *_: None)
    monkeypatch.setattr("app.api.source_management._consume_preview_token", lambda *_: None)

    async def fixture_cloud(*_: object, **__: object):
        return {
            "cloud_source_id": "shared-direct",
            "source_identity": source_identity("https://example.test/api"),
            "name": "Direct Shared",
            "base_url": "https://example.test/api",
            "parser": "api",
            "parser_config": {"default_category": "research"},
            "cloud_policy": "force_enabled",
            "crawl_interval_seconds": 3600,
            "reused": False,
            "preview": [{"title": "fixture"}],
        }

    monkeypatch.setattr("app.api.source_management._call_cloud_admin", fixture_cloud)
    result = await create_cloud_source(
        CloudSourceCreateRequest(
            admin_key="MOCK-FIXTURE-ADMIN",
            preview_token="fixture-token",
            name="Direct Shared",
            list_url="https://example.test/api",
            parser="api",
            category="research",
            crawl_interval_seconds=3600,
        ),
        db,
    )
    source = db.scalar(select(Source).where(Source.cloud_source_id == "shared-direct"))
    assert result["cloud_source_id"] == "shared-direct"
    assert source is not None and source.execution == "cloud" and source.ownership == "SHARED_CLOUD"
    monkeypatch.setattr(
        "app.crawler.runner.get_settings",
        lambda: SimpleNamespace(effective_deployment_role="desktop", public_feed_url="https://cloud.fixture.test/api/public/v1"),
    )
    config = CrawlerManager._load_source_configs(db)[0]
    assert config["parser"] == "cloud_feed"
    assert config["cloud_source_id"] == "shared-direct"
    db.close()


@pytest.mark.asyncio
async def test_desktop_promotion_maps_in_place_and_preserves_notice_state(monkeypatch: pytest.MonkeyPatch) -> None:
    db = make_session()
    local = Source(
        code="local-fixture",
        name="MOCK / FIXTURE HTML",
        base_url="https://example.test/notices",
        ownership="CUSTOM_LOCAL_PUBLIC",
        source_scope="personal",
        execution="local",
        parser="generic_html",
        parser_config="{}",
        validation_status="passed",
        validated_at=datetime(2026, 9, 2),
    )
    db.add(local)
    db.flush()
    notice = Notice(
        title="MOCK / FIXTURE notice",
        normalized_title="mockfixture",
        url="https://example.test/1",
        canonical_url="https://example.test/1",
        source_id=local.id,
        content="fixture",
        content_hash="a" * 64,
    )
    db.add(notice)
    db.flush()
    db.add(NoticeSourceRelation(notice_id=notice.id, source_id=local.id, source_url=notice.url, content_hash=notice.content_hash))
    db.add(UserState(notice_id=notice.id, is_read=True, is_favorite=True))
    db.commit()

    async def fixture_cloud(*_: object, **__: object):
        return {
            "cloud_source_id": "shared-fixture",
            "source_identity": source_identity(local.base_url),
            "cloud_policy": "force_enabled",
            "crawl_interval_seconds": None,
            "reused": True,
        }

    monkeypatch.setattr("app.api.source_management._call_cloud_admin", fixture_cloud)
    result = await promote_source(local.id, PromotionRequest(admin_key="MOCK-FIXTURE-ADMIN"), db)
    db.refresh(notice.user_state)
    assert result["promotion_reused"] is True
    assert local.id == notice.source_id and local.execution == "cloud"
    assert local.ownership == "SHARED_CLOUD" and local.cloud_source_id == "shared-fixture"
    assert notice.user_state is not None and notice.user_state.is_read and notice.user_state.is_favorite
    monkeypatch.setattr(
        "app.crawler.runner.get_settings",
        lambda: SimpleNamespace(effective_deployment_role="desktop", public_feed_url="https://cloud.fixture.test/api/public/v1"),
    )
    configs = CrawlerManager._load_source_configs(db)
    assert configs[0]["parser"] == "cloud_feed"
    assert configs[0]["cloud_source_id"] == "shared-fixture"
    db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/a",
        "http://10.0.0.1/a",
        "http://172.16.0.1/a",
        "http://192.168.1.1/a",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/a",
        "http://[fc00::1]/a",
        "file:///etc/passwd",
        "ftp://example.test/a",
        "gopher://example.test/a",
        "data:text/plain,hello",
        "javascript:alert(1)",
    ],
)
async def test_cloud_url_policy_blocks_ssrf_targets(url: str) -> None:
    with pytest.raises(UnsafeSourceUrl):
        await validate_source_url(url)


@pytest.mark.asyncio
async def test_safe_fetcher_revalidates_redirect_target(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fixture_validate(url: str, **_: object) -> str:
        if "127.0.0.1" in url:
            raise UnsafeSourceUrl("private redirect")
        return url

    monkeypatch.setattr("app.sources.generic.validate_source_url", fixture_validate)
    fetcher = SafeFetcher(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        )
    )
    fetcher.retries = 0
    with pytest.raises(SourceError, match="private redirect"):
        await fetcher.get("https://example.test/public")
    await fetcher.close()


@pytest.mark.asyncio
async def test_mock_authenticated_expiry_and_attachment_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def allow_fixture(url: str, **_: object) -> str:
        return url

    monkeypatch.setattr("app.sources.generic.validate_source_url", allow_fixture)
    expired = SafeFetcher(transport=httpx.MockTransport(lambda _: httpx.Response(401)))
    expired.auth_required = True
    expired.retries = 0
    with pytest.raises(LoginExpiredError, match="AUTH_SESSION_EXPIRED"):
        await expired.get("https://auth.fixture.test/notices")
    await expired.close()

    html = """<main class='content'>MOCK / FIXTURE authenticated notice</main>
    <a class='attachment' href='/files/mock.pdf'>mock.pdf</a>
    <a class='attachment' href='/files/mock.xlsx'>mock.xlsx</a>"""
    adapter = GenericPublicSource(
        {
            "code": "fixture",
            "name": "MOCK / FIXTURE",
            "base_url": "https://auth.fixture.test/notices",
            "parser": "generic_html",
            "parser_config": {"content_selector": ".content", "attachment_selector": ".attachment"},
        }
    )
    await adapter.fetcher.client.aclose()
    adapter.fetcher.client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=html))
    )
    detail = await adapter.fetch_detail(
        NoticeCandidate(title="MOCK / FIXTURE", url="https://auth.fixture.test/detail")
    )
    assert [(item.filename, item.type) for item in detail.attachments] == [
        ("mock.pdf", "pdf"),
        ("mock.xlsx", "xlsx"),
    ]
    await adapter.close()


def test_shared_cloud_feed_is_global_but_personal_source_is_not() -> None:
    db = make_session()
    shared = Source(
        code="shared-fixture",
        name="MOCK / FIXTURE Shared",
        base_url="https://example.test/shared",
        ownership="SHARED_CLOUD",
        source_scope="shared",
        execution="cloud",
        cloud_policy="force_enabled",
        source_identity="a" * 64,
    )
    personal = Source(
        code="personal-fixture",
        name="MOCK / FIXTURE Personal",
        base_url="https://example.test/personal",
        ownership="CUSTOM_LOCAL_PUBLIC",
        source_identity="b" * 64,
    )
    db.add_all([shared, personal])
    db.commit()
    result = public_sources(db)
    assert [item["id"] for item in result["items"]] == ["shared-fixture"]
    assert result["items"][0]["source_scope"] == "shared"
    db.close()
