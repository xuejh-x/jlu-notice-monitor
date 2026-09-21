from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.cloud.api import get_cloud_db
from app.cloud.main import app as cloud_app
from app.cloud.migration import migrate_public_data
from app.config import Settings, get_settings
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.database.migrations import run_phase15_cloud_data_migrations
from app.models import Attachment, Favorite, Notice, NoticeSourceRelation, NotificationEvent, Source, UserState
from app.paths import BACKEND_DIR
from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.retention import cleanup_notices


def make_memory_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def add_notice(
    db: Session,
    source: Source,
    *,
    title: str,
    score: int,
    published: date,
) -> Notice:
    notice = Notice(
        title=title,
        normalized_title=title.lower(),
        url=f"https://example.test/{title}",
        canonical_url=f"https://example.test/{title}",
        publish_date=published,
        source_id=source.id,
        content=f"{title} public body",
        content_hash=(title * 64)[:64],
        importance_score=score,
    )
    db.add(notice)
    db.flush()
    db.add(
        NoticeSourceRelation(
            notice_id=notice.id,
            source_id=source.id,
            source_url=notice.url,
            content_hash=notice.content_hash,
        )
    )
    return notice


def test_cloud_api_filters_paginates_and_returns_public_details() -> None:
    db = make_memory_session()
    public = Source(
        code="public", name="Public", base_url="https://example.test", ownership="OFFICIAL_CLOUD"
    )
    other = Source(
        code="other", name="Other", base_url="https://other.test", ownership="SHARED_CLOUD"
    )
    private = Source(
        code="private", name="Private", base_url="https://private.test", ownership="CUSTOM_LOCAL_PRIVATE"
    )
    db.add_all([public, other, private])
    db.flush()
    first = add_notice(db, public, title="Scholarship", score=90, published=date(2026, 9, 12))
    add_notice(db, public, title="Course", score=30, published=date(2026, 9, 11))
    add_notice(db, other, title="Competition", score=80, published=date(2026, 9, 10))
    add_notice(db, private, title="Private", score=100, published=date(2026, 9, 13))
    db.add(
        Attachment(
            notice_id=first.id,
            filename="guide.pdf",
            url="https://example.test/guide.pdf",
            type="pdf",
            content_hash="f" * 64,
        )
    )
    db.commit()

    def override_db():
        yield db

    cloud_app.dependency_overrides[get_cloud_db] = override_db
    try:
        client = TestClient(cloud_app)
        assert client.get("/health").json()["database"] == "ok"
        all_rows = client.get("/api/notices", params={"limit": 2})
        assert all_rows.status_code == 200
        assert all_rows.json()["total"] == 3
        assert all_rows.json()["total_pages"] == 2
        assert len(all_rows.json()["items"]) == 2

        filtered = client.get(
            "/api/notices",
            params={"source": "public", "importance": 70, "keyword": "Scholar"},
        )
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["id"] == first.id
        assert filtered.json()["items"][0]["version"] == 1

        detail = client.get(f"/api/notices/{first.id}")
        assert detail.status_code == 200
        assert detail.json()["content"] == "Scholarship public body"
        assert detail.json()["attachments"][0]["hash"] == "f" * 64
        assert client.get("/api/notices/99999").status_code == 404

        sources = client.get("/api/sources").json()["items"]
        assert {item["name"] for item in sources} == {"Public", "Other"}
    finally:
        cloud_app.dependency_overrides.clear()
        db.close()


def test_sqlite_to_cloud_migration_preserves_ids_and_is_idempotent() -> None:
    source_db = make_memory_session()
    target_db = make_memory_session()
    public = Source(
        id=17,
        code="public",
        name="Public",
        base_url="https://example.test",
        auth_username="must-not-migrate",
        credential_ref="secret-reference",
        session_profile_ref="private-profile",
        allow_private_network=True,
    )
    private = Source(
        id=18,
        code="private",
        name="Private",
        base_url="https://private.test",
        ownership="CUSTOM_LOCAL_PRIVATE",
    )
    source_db.add_all([public, private])
    source_db.flush()
    public_notice = add_notice(
        source_db, public, title="Migrated", score=70, published=date(2026, 9, 1)
    )
    private_notice = add_notice(
        source_db, private, title="Personal", score=20, published=date(2026, 9, 1)
    )
    source_db.add_all(
        [
            Attachment(
                notice_id=public_notice.id,
                filename="a.pdf",
                url="https://example.test/a.pdf",
                type="pdf",
            ),
            UserState(notice_id=public_notice.id, is_read=True, is_favorite=True),
            Favorite(notice_id=public_notice.id),
        ]
    )
    source_db.commit()

    first = migrate_public_data(source_db, target_db)
    second = migrate_public_data(source_db, target_db)
    assert first == second
    assert first.sources == 1 and first.notices == 1 and first.attachments == 1
    migrated = target_db.get(Notice, public_notice.id)
    assert migrated is not None and migrated.source_id == 17
    migrated_source = target_db.get(Source, 17)
    assert migrated_source is not None
    assert migrated_source.auth_username is None
    assert migrated_source.credential_ref is None
    assert migrated_source.session_profile_ref is None
    assert migrated_source.allow_private_network is False
    assert target_db.get(Notice, private_notice.id) is None
    assert target_db.scalars(select(UserState)).all() == []
    assert target_db.scalars(select(Favorite)).all() == []
    assert len(target_db.scalars(select(Notice)).all()) == 1
    source_db.close()
    target_db.close()


def test_cloud_crawler_writes_public_facts_without_client_state(monkeypatch) -> None:
    db = make_memory_session()
    source = Source(code="cloud", name="Cloud", base_url="https://example.test")
    db.add(source)
    db.commit()
    monkeypatch.setattr(
        "app.crawler.runner.get_settings",
        lambda: Settings(_env_file=None, deployment_role="cloud"),
    )
    candidate = NoticeCandidate(
        title="Cloud notice",
        url="https://example.test/notice",
        content="first version",
        attachments=[
            AttachmentData(filename="guide.pdf", url="https://example.test/guide.pdf", type="pdf")
        ],
    )
    assert CrawlerManager._persist_candidate(db, source, candidate, False) == "NEW"
    assert CrawlerManager._persist_candidate(
        db, source, candidate.model_copy(update={"content": "second version"}), False
    ) == "UPDATED"
    notice = db.scalar(select(Notice))
    attachment = db.scalar(select(Attachment))
    assert notice is not None and notice.version == 2
    assert attachment is not None and attachment.content_hash is not None
    assert db.scalars(select(UserState)).all() == []
    assert db.scalars(select(NotificationEvent)).all() == []
    db.close()


def test_phase15_sqlite_additive_migration_is_repeatable(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE notices (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE attachments (id INTEGER PRIMARY KEY, notice_id INTEGER, "
                "filename VARCHAR(1000), url VARCHAR(2000), type VARCHAR(20), extracted_text TEXT)"
            )
        )
        connection.execute(
            text("CREATE TABLE schema_migrations (version VARCHAR(40) PRIMARY KEY, applied_at DATETIME)")
        )
        connection.execute(text("INSERT INTO notices (id) VALUES (1)"))
        connection.execute(
            text(
                "INSERT INTO attachments (id, notice_id, filename, url, type) "
                "VALUES (1, 1, 'a.pdf', 'https://example.test/a.pdf', 'pdf')"
            )
        )
    run_phase15_cloud_data_migrations(engine)
    run_phase15_cloud_data_migrations(engine)
    assert {item["name"] for item in inspect(engine).get_columns("notices")} >= {"version"}
    assert {item["name"] for item in inspect(engine).get_columns("attachments")} >= {
        "content_hash",
        "created_at",
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version FROM notices WHERE id = 1")) == 1
        assert connection.scalar(text("SELECT created_at FROM attachments WHERE id = 1")) is not None
        assert connection.scalar(
            text("SELECT COUNT(*) FROM schema_migrations WHERE version = 'phase-1.5'")
        ) == 1
    engine.dispose()


def test_alembic_bootstraps_only_cloud_tables(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cloud.db"
    monkeypatch.setenv("JLU_DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()
    tables = set(inspect(create_engine(f"sqlite:///{database_path.as_posix()}")).get_table_names())
    assert {
        "alembic_version",
        "sources",
        "notices",
        "attachments",
        "notice_source_relations",
        "notice_updates",
        "importance_rules",
        "app_state",
    } <= tables
    assert {"user_states", "favorites", "notification_events", "notification_deliveries"}.isdisjoint(tables)
    cloud_engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with Session(cloud_engine) as db:
        source = Source(code="retention-cloud", name="Cloud", base_url="https://example.test")
        db.add(source)
        db.flush()
        db.add(
            Notice(
                title="Old cloud fact",
                normalized_title="oldcloudfact",
                url="https://example.test/old",
                canonical_url="https://example.test/old",
                publish_date=date(2020, 1, 1),
                source_id=source.id,
                content_hash="o" * 64,
            )
        )
        db.commit()
        result = cleanup_notices(
            db,
            Settings(_env_file=None, deployment_role="cloud"),
            now=datetime.now() + timedelta(days=366),
        )
        db.commit()
        assert result.deleted_count == 1
    cloud_engine.dispose()
