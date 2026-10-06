from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from app.models import AppState, Attachment, Favorite, Notice, NotificationDelivery, NotificationEvent, NoticeSourceRelation, Source, UserState
from app.services.retention import LAST_CLEANUP_KEY, cleanup_notices, storage_status


NOW = datetime(2026, 9, 13, 12, 0, 0)


def add_notice(
    db: Session, source: Source, *, title: str, publish_date: date, score: int = 40,
    read: bool = True, favorite: bool = False,
) -> Notice:
    notice = Notice(
        title=title, normalized_title=title, url=f"https://example.test/{title}",
        canonical_url=f"https://example.test/{title}", publish_date=publish_date,
        source_id=source.id, content_hash=title * 8, importance_score=score,
    )
    db.add(notice)
    db.flush()
    db.add(NoticeSourceRelation(notice_id=notice.id, source_id=source.id, source_url=notice.url, content_hash=notice.content_hash))
    db.add(UserState(notice_id=notice.id, is_read=read, is_favorite=favorite))
    if favorite:
        db.add(Favorite(notice_id=notice.id))
    return notice


def test_local_retention_deletes_all_dated_old_notices_and_dependent_data() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine)
    source = Source(code="retention", name="Retention", base_url="https://example.test")
    db.add(source); db.flush()
    old = add_notice(db, source, title="old", publish_date=(NOW - timedelta(days=366)).date())
    recent = add_notice(db, source, title="recent", publish_date=(NOW - timedelta(days=30)).date())
    unread = add_notice(db, source, title="unread", publish_date=(NOW - timedelta(days=366)).date(), read=False)
    favorite = add_notice(db, source, title="favorite", publish_date=(NOW - timedelta(days=366)).date(), favorite=True)
    important = add_notice(db, source, title="important", publish_date=(NOW - timedelta(days=366)).date(), score=80)
    db.add(Attachment(notice_id=old.id, filename="old.pdf", url="https://example.test/old.pdf", type="pdf"))
    event = NotificationEvent(dedupe_key="retention-old", event_type="NEW_NOTICE", notice_id=old.id, title="old", body="old")
    db.add(event); db.flush()
    db.add(NotificationDelivery(event_id=event.id))
    db.commit()

    settings = Settings(_env_file=None, deployment_role="desktop")
    assert storage_status(db, settings, now=NOW)["cleanup_candidates"] == 4
    assert storage_status(db, settings, now=NOW)["preserves_local_exceptions"] is False
    result = cleanup_notices(db, settings, now=NOW)
    db.commit()

    assert result.deleted_count == 4
    assert all(db.get(Notice, item.id) is None for item in (old, unread, favorite, important))
    assert db.get(Notice, recent.id) is not None
    assert db.scalars(select(Favorite)).all() == []
    assert db.scalars(select(Attachment).where(Attachment.notice_id == old.id)).all() == []
    assert db.scalars(select(NotificationEvent).where(NotificationEvent.notice_id == old.id)).all() == []
    assert db.scalars(select(NotificationDelivery)).all() == []
    assert db.get(Source, source.id) is not None
    assert db.get(AppState, LAST_CLEANUP_KEY) is not None
    assert cleanup_notices(db, settings, now=NOW).deleted_count == 0
    db.close(); engine.dispose()


def test_cloud_retention_has_no_local_state_exceptions() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine)
    source = Source(code="cloud-retention", name="Retention", base_url="https://example.test")
    db.add(source); db.flush()
    old_unread = add_notice(db, source, title="old-unread", publish_date=(NOW - timedelta(days=366)).date(), read=False)
    old_favorite = add_notice(db, source, title="old-favorite", publish_date=(NOW - timedelta(days=366)).date(), favorite=True)
    old_important = add_notice(db, source, title="old-important", publish_date=(NOW - timedelta(days=366)).date(), score=100)
    db.commit()
    old_ids = (old_unread.id, old_favorite.id, old_important.id)

    result = cleanup_notices(db, Settings(_env_file=None, deployment_role="cloud"), now=NOW)
    db.commit()
    assert result.deleted_count == 3
    assert all(db.get(Notice, notice_id) is None for notice_id in old_ids)
    db.close(); engine.dispose()


def test_storage_status_and_manual_cleanup_api_refresh_counts() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine)
    source = Source(code="status", name="Status", base_url="https://example.test")
    db.add(source); db.flush()
    add_notice(db, source, title="candidate", publish_date=(date.today() - timedelta(days=366)))
    add_notice(db, source, title="unread", publish_date=(date.today() - timedelta(days=366)), read=False)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        before = client.get("/api/storage/status")
        assert before.status_code == 200
        assert before.json()["total_notifications"] == 2
        assert before.json()["cleanup_candidates"] == 2
        assert before.json()["database_size_bytes"] > 0
        cleaned = client.post("/api/storage/cleanup")
        assert cleaned.status_code == 200
        assert cleaned.json()["deleted_count"] == 2
        assert cleaned.json()["total_notifications"] == 0
        assert cleaned.json()["cleanup_candidates"] == 0
        assert cleaned.json()["last_cleanup_at"] is not None
    finally:
        app.dependency_overrides.clear()
        db.close(); engine.dispose()
