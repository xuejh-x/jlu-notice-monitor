from __future__ import annotations

from datetime import datetime
import sqlite3
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.public_feed import public_sources
from app.api.source_management import list_source_configuration
from app.crawler.runner import CrawlRunResult, CrawlerManager, SourceRunResult
from app.database import Base
from app.database.migrations import run_stage17_1_migrations
from app.models import Source
import app.crawler.runner as runner_module


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_source_model_defaults_execution_policy_from_ownership() -> None:
    with make_session() as db:
        sources = [
            Source(code="official", name="Official", base_url="https://official.test", ownership="OFFICIAL_CLOUD"),
            Source(code="shared", name="Shared", base_url="https://shared.test", ownership="SHARED_CLOUD"),
            Source(code="local", name="Local", base_url="https://local.test", ownership="CUSTOM_LOCAL_PUBLIC"),
        ]
        db.add_all(sources)
        db.commit()
        assert [source.execution_policy for source in sources] == [
            "cloud_preferred",
            "cloud_only",
            "local_only",
        ]


def test_stage17_1_migration_is_additive_and_preserves_execution(tmp_path) -> None:
    path = tmp_path / "stage17-1.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sources (
          id INTEGER PRIMARY KEY, ownership VARCHAR(40) NOT NULL,
          execution VARCHAR(20) NOT NULL
        );
        CREATE TABLE schema_migrations (version VARCHAR(40) PRIMARY KEY, applied_at DATETIME);
        INSERT INTO sources VALUES (1, 'OFFICIAL_CLOUD', 'cloud');
        INSERT INTO sources VALUES (2, 'SHARED_CLOUD', 'cloud');
        INSERT INTO sources VALUES (3, 'CUSTOM_LOCAL_PRIVATE', 'local');
        """
    )
    connection.commit()
    connection.close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")

    run_stage17_1_migrations(engine)
    run_stage17_1_migrations(engine)

    assert "execution_policy" in {column["name"] for column in inspect(engine).get_columns("sources")}
    with engine.connect() as db:
        rows = db.exec_driver_sql(
            "SELECT ownership, execution, execution_policy FROM sources ORDER BY id"
        ).all()
        versions = {row[0] for row in db.exec_driver_sql("SELECT version FROM schema_migrations")}
    assert rows == [
        ("OFFICIAL_CLOUD", "cloud", "cloud_preferred"),
        ("SHARED_CLOUD", "cloud", "cloud_only"),
        ("CUSTOM_LOCAL_PRIVATE", "local", "local_only"),
    ]
    assert versions == {"17.1"}


def test_source_apis_expose_execution_policy() -> None:
    with make_session() as db:
        db.add_all([
            Source(
                code="official",
                name="Official",
                base_url="https://official.test",
                ownership="OFFICIAL_CLOUD",
                source_scope="official",
                execution="cloud",
            ),
            Source(
                code="shared",
                name="Shared",
                base_url="https://shared.test",
                ownership="SHARED_CLOUD",
                source_scope="shared",
                execution="cloud",
            ),
        ])
        db.commit()

        local_payload = list_source_configuration(db)
        public_payload = public_sources(db)

    assert {item["code"]: item["execution_policy"] for item in local_payload} == {
        "official": "cloud_preferred",
        "shared": "cloud_only",
    }
    assert {item["code"]: item["execution_policy"] for item in public_payload["items"]} == {
        "official": "cloud_preferred",
        "shared": "cloud_only",
    }


def test_source_registry_assigns_policy_without_changing_effective_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        runner_module,
        "get_settings",
        lambda: SimpleNamespace(effective_deployment_role="desktop", public_feed_url=None),
    )
    with make_session() as db:
        CrawlerManager._sync_sources(db, [
            {
                "code": "official",
                "name": "Official",
                "base_url": "https://official.test",
                "parser": "auto",
                "ownership": "OFFICIAL_CLOUD",
                "execution": "cloud",
            },
            {
                "code": "shared",
                "name": "Shared",
                "base_url": "https://shared.test",
                "parser": "auto",
                "ownership": "SHARED_CLOUD",
                "execution": "cloud",
            },
            {
                "code": "local",
                "name": "Local",
                "base_url": "https://local.test",
                "parser": "auto",
                "ownership": "CUSTOM_LOCAL_PUBLIC",
                "execution": "local",
            },
        ])
        configs = CrawlerManager._load_source_configs(db)
        rows = {source.code: source for source in db.scalars(select(Source)).all()}

    assert (rows["official"].execution, rows["official"].execution_policy) == ("cloud", "cloud_preferred")
    assert (rows["shared"].execution, rows["shared"].execution_policy) == ("cloud", "cloud_only")
    assert (rows["local"].execution, rows["local"].execution_policy) == ("local", "local_only")
    resolved = {config["code"]: config for config in configs}
    assert resolved["official"]["parser"] == "cloud_feed"
    assert resolved["official"]["effective_execution"] == "cloud"
    assert resolved["shared"]["effective_execution"] == "cloud"
    assert resolved["local"]["effective_execution"] == "local"


def test_crawler_status_exposes_policy_and_effective_execution(tmp_path) -> None:
    manager = CrawlerManager(cache_dir=tmp_path)
    manager.last_result = CrawlRunResult(
        started_at=datetime(2026, 9, 12, 8, 0, 0),
        finished_at=datetime(2026, 9, 12, 8, 0, 1),
        status="success",
        source_results=[
            SourceRunResult(
                source="oa",
                execution_policy="cloud_preferred",
                effective_execution="cloud",
                status="success",
            )
        ],
    )

    result = manager.status()["source_results"][0]
    assert result["execution_policy"] == "cloud_preferred"
    assert result["effective_execution"] == "cloud"
