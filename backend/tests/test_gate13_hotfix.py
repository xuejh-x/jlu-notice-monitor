from __future__ import annotations

import socket
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes import sources as list_sources
from app.api.source_management import _serialize_source
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Source
from app.services.source_security import (
    UnsafeSourceUrl,
    validate_cloud_source_url,
    validate_local_source_url,
)
from app.sources.base import SourceError
from app.sources.generic import SafeFetcher


def _fake_ip_record() -> list[tuple[object, ...]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.1.29", 0))]


@pytest.mark.asyncio
async def test_local_hostname_with_fake_ip_dns_reaches_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    dns_calls = 0
    fetch_calls = 0

    def fake_dns(*_: object, **__: object) -> list[tuple[object, ...]]:
        nonlocal dns_calls
        dns_calls += 1
        return _fake_ip_record()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetch_calls
        fetch_calls += 1
        assert request.url.host == "example-public.test"
        return httpx.Response(200, text="MOCK / FIXTURE public source")

    monkeypatch.setattr("app.services.source_security.socket.getaddrinfo", fake_dns)
    fetcher = SafeFetcher(validation_scope="local", transport=httpx.MockTransport(handler))
    fetcher.retries = 0
    body, _, _ = await fetcher.get("https://example-public.test/notices")
    await fetcher.close()

    assert body == "MOCK / FIXTURE public source"
    assert fetch_calls == 1
    assert dns_calls == 0


@pytest.mark.asyncio
async def test_local_direct_fake_ip_literal_remains_blocked() -> None:
    with pytest.raises(UnsafeSourceUrl, match="Local and private"):
        await validate_local_source_url("http://198.18.1.29/")


@pytest.mark.asyncio
async def test_cloud_hostname_resolving_to_fake_ip_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.source_security.socket.getaddrinfo",
        lambda *_args, **_kwargs: _fake_ip_record(),
    )
    with pytest.raises(UnsafeSourceUrl, match="Local and private"):
        await validate_cloud_source_url("https://example-public.test/notices")


@pytest.mark.asyncio
async def test_cloud_direct_fake_ip_literal_remains_blocked() -> None:
    with pytest.raises(UnsafeSourceUrl, match="Local and private"):
        await validate_cloud_source_url("http://198.18.1.29/")


@pytest.mark.asyncio
async def test_cloud_redirect_to_fake_ip_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.source_security.socket.getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )
    fetcher = SafeFetcher(
        validation_scope="cloud",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"location": "http://198.18.1.29/private"})
        ),
    )
    fetcher.retries = 0
    with pytest.raises(SourceError, match="Local and private"):
        await fetcher.get("https://example-public.test/notices")
    await fetcher.close()


def test_public_feed_not_configured_projects_to_neutral_health_reason() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        source = Source(
            code="official-fixture",
            name="MOCK / FIXTURE official source",
            base_url="https://example-public.test/notices",
            ownership="OFFICIAL_CLOUD",
            source_scope="official",
            execution="cloud",
            health_state="source_error",
            last_error_code="SOURCE_ERROR",
            last_error="SourceError: PUBLIC_FEED_NOT_CONFIGURED",
        )
        db.add(source)
        db.commit()
        configured = _serialize_source(source)
        public = list_sources(db)[0]

    assert configured["health_state"] == "cloud_unconfigured"
    assert configured["last_error_code"] == "PUBLIC_FEED_NOT_CONFIGURED"
    assert configured["last_error"] is None
    assert public["status"] == "cloud_unconfigured"
    assert public["message"] == "等待 Notice Hub 公共源启用"
    assert public["last_error"] is None


def test_crawler_configuration_selects_validation_boundary_by_runtime_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        cloud = Source(
            code="shared-fixture",
            name="MOCK / FIXTURE shared source",
            base_url="https://example-public.test/notices",
            ownership="SHARED_CLOUD",
            source_scope="shared",
            execution="cloud",
            parser="rss",
            subscribed=True,
        )
        local = Source(
            code="local-fixture",
            name="MOCK / FIXTURE local source",
            base_url="https://example-public.test/local",
            ownership="CUSTOM_LOCAL_PUBLIC",
            source_scope="personal",
            execution="local",
            parser="rss",
        )
        db.add_all([cloud, local])
        db.commit()

        monkeypatch.setattr(
            "app.crawler.runner.get_settings",
            lambda: SimpleNamespace(effective_deployment_role="cloud", public_feed_url=None),
        )
        cloud_configs = CrawlerManager._load_source_configs(db)
        assert len(cloud_configs) == 1
        assert cloud_configs[0]["validation_scope"] == "cloud"

        monkeypatch.setattr(
            "app.crawler.runner.get_settings",
            lambda: SimpleNamespace(effective_deployment_role="desktop", public_feed_url=None),
        )
        desktop_configs = CrawlerManager._load_source_configs(db)
        local_config = next(item for item in desktop_configs if item["code"] == "local-fixture")
        assert local_config["validation_scope"] == "local"
