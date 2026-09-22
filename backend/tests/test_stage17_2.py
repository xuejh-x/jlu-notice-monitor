from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.crawler.runner as runner_module
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.database.migrations import run_stage17_2_migrations
from app.models import AppState, Notice, NotificationEvent, NotificationPreference, Source, UserState
from app.schemas.notice import NoticeCandidate
from app.services.notice_identity import origin_item_key
from app.sources.base import SourceError
from app.sources.cloud import CloudFeedSource, PUBLIC_FEED_EXPIRED, PUBLIC_FEED_NETWORK_ERROR


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def desktop_settings() -> SimpleNamespace:
    return SimpleNamespace(
        effective_deployment_role="desktop",
        source_run_timeout_seconds=120,
        bootstrap_recent_days=7,
    )


def cloud_preferred_config() -> dict[str, object]:
    return {
        "code": "official",
        "name": "Official",
        "base_url": "https://official.test",
        "ownership": "OFFICIAL_CLOUD",
        "execution": "cloud",
        "execution_policy": "cloud_preferred",
        "effective_execution": "cloud",
        "parser": "cloud_feed",
        "fallback_parser": "oa_public",
    }


class FixtureAdapter:
    def __init__(
        self,
        items: list[NoticeCandidate] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.items = items or []
        self.error = error

    async def fetch_list(self) -> list[NoticeCandidate]:
        if self.error:
            raise self.error
        return self.items

    async def fetch_detail(self, item: NoticeCandidate) -> NoticeCandidate:
        return item

    async def close(self) -> None:
        return None


def configure_run(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    adapters: dict[str, FixtureAdapter],
    calls: list[str],
) -> None:
    monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(runner_module, "get_settings", desktop_settings)

    def build(config: dict[str, object]) -> FixtureAdapter:
        parser = str(config["parser"])
        calls.append(parser)
        return adapters[parser]

    monkeypatch.setattr(runner_module, "build_source", build)


@pytest.mark.asyncio
async def test_cloud_success_does_not_fallback_even_when_feed_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with make_session() as db:
        db.add(Source(code="official", name="Official", base_url="https://official.test"))
        db.commit()
        calls: list[str] = []
        configure_run(
            monkeypatch,
            db,
            {"cloud_feed": FixtureAdapter([]), "oa_public": FixtureAdapter(error=AssertionError())},
            calls,
        )

        result = await CrawlerManager(tmp_path)._run_source(cloud_preferred_config(), False)

        assert result.status == "success"
        assert result.fallback_used is False and result.fallback_reason is None
        assert result.effective_execution == "cloud"
        assert [(attempt.execution, attempt.status) for attempt in result.attempts] == [
            ("cloud", "success")
        ]
        assert calls == ["cloud_feed"]


@pytest.mark.asyncio
async def test_cloud_failure_falls_back_to_local_and_produces_one_final_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = NoticeCandidate(
        public_id="official-42",
        title="Fallback notice",
        url="https://official.test/notices/42",
        content="body",
    )
    with make_session() as db:
        db.add(Source(code="official", name="Official", base_url="https://official.test"))
        db.commit()
        calls: list[str] = []
        configure_run(
            monkeypatch,
            db,
            {
                "cloud_feed": FixtureAdapter(error=SourceError(PUBLIC_FEED_NETWORK_ERROR)),
                "oa_public": FixtureAdapter([item]),
            },
            calls,
        )

        db.add(NotificationPreference(id=1, enabled=True))
        db.commit()
        result = await CrawlerManager(tmp_path)._run_source(cloud_preferred_config(), False)

        assert result.status == "success" and result.new_count == 0
        assert result.unchanged_count == 1
        assert result.effective_execution == "local"
        assert result.fallback_used is True
        assert result.fallback_reason == PUBLIC_FEED_NETWORK_ERROR
        assert [(attempt.execution, attempt.status) for attempt in result.attempts] == [
            ("cloud", "failure"),
            ("local", "success"),
        ]
        assert calls == ["cloud_feed", "oa_public"]
        assert db.scalar(select(Notice)).status == "baseline"
        assert db.scalar(select(UserState)).is_read is True
        assert db.scalar(select(NotificationEvent)) is None
        assert db.get(AppState, "local-fallback-baseline:1") is not None


@pytest.mark.asyncio
async def test_local_fallback_baseline_makes_later_items_new_and_unread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    historical = NoticeCandidate(
        public_id="official-old",
        title="Historical fallback notice",
        url="https://official.test/notices/old",
        content="old body",
    )
    new = NoticeCandidate(
        public_id="official-new",
        title="New fallback notice",
        url="https://official.test/notices/new",
        content="new body",
    )
    with make_session() as db:
        db.add(Source(code="official", name="Official", base_url="https://official.test"))
        db.add(NotificationPreference(id=1, enabled=True))
        db.commit()
        calls: list[str] = []
        cloud = FixtureAdapter(error=SourceError(PUBLIC_FEED_NETWORK_ERROR))
        local = FixtureAdapter([historical])
        configure_run(monkeypatch, db, {"cloud_feed": cloud, "oa_public": local}, calls)
        manager = CrawlerManager(tmp_path)

        first = await manager._run_source(cloud_preferred_config(), False)
        local.items = [historical, new]
        second = await manager._run_source(cloud_preferred_config(), False)

        assert first.new_count == 0
        assert second.new_count == 1
        new_notice = db.scalar(select(Notice).where(Notice.public_id == "official-new"))
        assert new_notice is not None
        assert db.scalar(select(UserState).where(UserState.notice_id == new_notice.id)).is_read is False
        assert db.scalar(select(NotificationEvent).where(NotificationEvent.notice_id == new_notice.id)) is not None


@pytest.mark.asyncio
async def test_failed_or_empty_local_fallback_does_not_establish_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with make_session() as db:
        db.add(Source(code="official", name="Official", base_url="https://official.test"))
        db.commit()
        calls: list[str] = []
        configure_run(
            monkeypatch,
            db,
            {
                "cloud_feed": FixtureAdapter(error=SourceError(PUBLIC_FEED_NETWORK_ERROR)),
                "oa_public": FixtureAdapter([]),
            },
            calls,
        )

        result = await CrawlerManager(tmp_path)._run_source(cloud_preferred_config(), False)

        assert result.status == "success"
        assert db.get(AppState, "local-fallback-baseline:1") is None


@pytest.mark.asyncio
async def test_cloud_failure_and_local_failure_return_one_failed_source_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with make_session() as db:
        db.add(Source(code="official", name="Official", base_url="https://official.test"))
        db.commit()
        calls: list[str] = []
        configure_run(
            monkeypatch,
            db,
            {
                "cloud_feed": FixtureAdapter(error=SourceError(PUBLIC_FEED_NETWORK_ERROR)),
                "oa_public": FixtureAdapter(error=SourceError("GET origin failed")),
            },
            calls,
        )

        result = await CrawlerManager(tmp_path)._run_source(cloud_preferred_config(), False)

        assert result.status == "failure"
        assert result.fallback_used is True and result.effective_execution == "local"
        assert len(result.attempts) == 2
        assert [attempt.status for attempt in result.attempts] == ["failure", "failure"]
        assert len(result.errors) == 2
        assert calls == ["cloud_feed", "oa_public"]
        assert db.get(AppState, "local-fallback-baseline:1") is None


@pytest.mark.asyncio
async def test_shared_cloud_source_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with make_session() as db:
        db.add(
            Source(
                code="official",
                name="Shared",
                base_url="https://shared.test",
                ownership="SHARED_CLOUD",
            )
        )
        db.commit()
        calls: list[str] = []
        configure_run(
            monkeypatch,
            db,
            {
                "cloud_feed": FixtureAdapter(error=SourceError(PUBLIC_FEED_NETWORK_ERROR)),
                "oa_public": FixtureAdapter([]),
            },
            calls,
        )
        config = {
            **cloud_preferred_config(),
            "ownership": "SHARED_CLOUD",
            "execution_policy": "cloud_only",
        }

        result = await CrawlerManager(tmp_path)._run_source(config, False)

        assert result.status == "failure" and result.fallback_used is False
        assert len(result.attempts) == 1
        assert calls == ["cloud_feed"]


@pytest.mark.asyncio
async def test_cloud_recovery_after_local_fallback_does_not_recreate_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://official.test/notices/42?utm_source=cloud"
    local_item = NoticeCandidate(
        public_id="official-42", title="Same notice", url=url, content="body"
    )
    cloud_item = NoticeCandidate(
        public_id="legacy-public-feed-id",
        origin_item_key=origin_item_key("official-42", url),
        title="Same notice",
        url=url,
        content="body",
    )
    with make_session() as db:
        db.add(Source(code="official", name="Official", base_url="https://official.test"))
        db.add(NotificationPreference(id=1, enabled=True))
        db.commit()
        calls: list[str] = []
        cloud = FixtureAdapter(error=SourceError(PUBLIC_FEED_NETWORK_ERROR))
        configure_run(
            monkeypatch,
            db,
            {"cloud_feed": cloud, "oa_public": FixtureAdapter([local_item])},
            calls,
        )
        manager = CrawlerManager(tmp_path)

        first = await manager._run_source(cloud_preferred_config(), False)
        cloud.error = None
        cloud.items = [cloud_item]
        second = await manager._run_source(cloud_preferred_config(), False)

        assert first.new_count == 0 and first.fallback_used is True
        assert second.unchanged_count == 1 and second.fallback_used is False
        assert len(db.scalars(select(Notice)).all()) == 1
        assert db.scalar(select(UserState)).is_read is True
        assert db.get(AppState, "local-fallback-baseline:1") is not None
        assert len(db.scalars(select(NotificationEvent)).all()) == 0


@pytest.mark.asyncio
async def test_new_source_first_local_fallback_uses_its_own_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = {**cloud_preferred_config(), "code": "new-source", "cloud_source_id": "new-source"}
    item = NoticeCandidate(
        public_id="new-source-old",
        title="Historical notice for a newly added source",
        url="https://official.test/notices/new-source-old",
        content="body",
    )
    with make_session() as db:
        db.add(Source(code="new-source", name="New source", base_url="https://official.test"))
        db.commit()
        calls: list[str] = []
        configure_run(
            monkeypatch,
            db,
            {
                "cloud_feed": FixtureAdapter(error=SourceError(PUBLIC_FEED_NETWORK_ERROR)),
                "oa_public": FixtureAdapter([item]),
            },
            calls,
        )

        result = await CrawlerManager(tmp_path)._run_source(config, False)

        assert result.new_count == 0
        assert db.scalar(select(UserState)).is_read is True
        assert db.get(AppState, "local-fallback-baseline:1") is not None


def test_origin_item_key_prefers_native_id_then_canonical_url_hash() -> None:
    assert origin_item_key("source-123", "https://example.test/one") == "native:source-123"
    assert origin_item_key(None, "HTTPS://EXAMPLE.TEST/a?utm_source=x") == origin_item_key(
        None, "https://example.test/a"
    )


def test_cloud_feed_expired_metadata_is_fallback_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.sources.cloud.get_settings",
        lambda: SimpleNamespace(cloud_feed_stale_after_seconds=3600),
    )
    payload = {
        "source_last_success_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    }
    with pytest.raises(SourceError, match=PUBLIC_FEED_EXPIRED):
        CloudFeedSource._validate_freshness(payload)


def test_stage17_2_migration_backfills_origin_item_key(tmp_path: Path) -> None:
    path = tmp_path / "stage17-2.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE notice_source_relations (
          id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, source_url VARCHAR(2000) NOT NULL
        );
        CREATE TABLE schema_migrations (version VARCHAR(40) PRIMARY KEY, applied_at DATETIME);
        INSERT INTO notice_source_relations VALUES (1, 2, 'https://example.test/a?utm_source=old');
        """
    )
    connection.commit()
    connection.close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")

    run_stage17_2_migrations(engine)
    run_stage17_2_migrations(engine)

    assert "origin_item_key" in {
        column["name"] for column in inspect(engine).get_columns("notice_source_relations")
    }
    with engine.connect() as db:
        key = db.exec_driver_sql(
            "SELECT origin_item_key FROM notice_source_relations WHERE id = 1"
        ).scalar_one()
        versions = {row[0] for row in db.exec_driver_sql("SELECT version FROM schema_migrations")}
    assert key == origin_item_key(None, "https://example.test/a")
    assert versions == {"17.2"}
