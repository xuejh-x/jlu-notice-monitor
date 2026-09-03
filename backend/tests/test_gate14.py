from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import sqlite3
from types import SimpleNamespace

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.database.migrations import run_gate14_migrations
from app.models import (
    Notice,
    NotificationDelivery,
    NotificationEvent,
    NotificationPreference,
    Source,
    UserState,
)
from app.services import notifications
from app.api import notifications as notification_api


def make_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def enable(db: Session) -> NotificationPreference:
    value = notifications.ensure_preferences(db)
    value.enabled = True
    db.commit()
    return value


def add_notice(
    db: Session, *, score: int = 50, deadline: date | None = None, first_seen_at: datetime | None = None
) -> Notice:
    source = db.scalar(select(Source).where(Source.code == "fixture"))
    if source is None:
        source = Source(code="fixture", name="MOCK / FIXTURE", base_url="https://example.test")
        db.add(source)
        db.flush()
    notice = Notice(
        title="MOCK / FIXTURE notification",
        normalized_title="mock fixture notification",
        url=f"https://example.test/{score}/{deadline}",
        canonical_url=f"https://example.test/{score}/{deadline}",
        source_id=source.id,
        content="fixture",
        content_hash=f"{score:064d}"[-64:],
        importance_score=score,
        registration_deadline=deadline,
        first_seen_at=first_seen_at or notifications.utcnow(),
        status="active",
    )
    db.add(notice)
    db.flush()
    db.add(UserState(notice_id=notice.id, is_read=False))
    db.flush()
    return notice


def desktop(monkeypatch) -> None:
    monkeypatch.setattr(
        notifications,
        "get_settings",
        lambda: SimpleNamespace(effective_deployment_role="desktop"),
    )


def test_new_and_important_event_creation_dedupe_and_filtering(monkeypatch) -> None:
    desktop(monkeypatch)
    db = make_session()
    preferences = enable(db)
    important = add_notice(db, score=80)
    first = notifications.record_notice_event(db, important, "NEW")
    second = notifications.record_notice_event(db, important, "NEW")
    assert [item.event_type for item in first] == ["IMPORTANT_NOTICE"]
    assert second == []
    preferences.important_notice_enabled = False
    preferences.new_notice_enabled = False
    ordinary = add_notice(db, score=20)
    assert notifications.record_notice_event(db, ordinary, "NEW") == []
    assert len(db.scalars(select(NotificationEvent)).all()) == 1
    db.close()


def test_deadline_changed_and_lead_day_are_unique(monkeypatch) -> None:
    desktop(monkeypatch)
    db = make_session()
    enable(db)
    current = datetime(2026, 9, 3, 10, tzinfo=UTC)
    notice = add_notice(db, deadline=date(2026, 9, 10))
    assert notifications.generate_scheduled_events(db, current_local=current)
    assert notifications.generate_scheduled_events(db, current_local=current) == []
    notice.registration_deadline = date(2026, 9, 11)
    changed = notifications.record_notice_event(
        db, notice, "UPDATED", old_deadline=date(2026, 9, 10), current_local=current
    )
    assert [item.event_type for item in changed] == ["DEADLINE_CHANGED"]
    keys = {item.dedupe_key for item in db.scalars(select(NotificationEvent)).all()}
    assert f"DEADLINE_APPROACHING:{notice.id}:2026-09-10:7" in keys
    assert f"DEADLINE_CHANGED:{notice.id}:2026-09-10:2026-09-11" in keys
    db.close()


def test_daily_summary_uses_local_date_and_is_unique(monkeypatch) -> None:
    desktop(monkeypatch)
    db = make_session()
    enable(db)
    current = datetime(2026, 9, 3, 9, 1, tzinfo=UTC)
    add_notice(db, score=80, first_seen_at=datetime(2026, 9, 3, 1))
    notifications.generate_scheduled_events(db, current_local=current)
    notifications.generate_scheduled_events(db, current_local=current)
    summaries = db.scalars(
        select(NotificationEvent).where(NotificationEvent.event_type == "DAILY_SUMMARY")
    ).all()
    assert len(summaries) == 1
    assert summaries[0].dedupe_key == "DAILY_SUMMARY:2026-09-03"
    assert "新增 1" in summaries[0].body and "重要 1" in summaries[0].body
    db.close()


def test_delivery_survives_restart_and_is_not_reclaimed(tmp_path, monkeypatch) -> None:
    desktop(monkeypatch)
    path = tmp_path / "restart.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        enable(db)
        notice = add_notice(db)
        notifications.record_notice_event(
            db, notice, "NEW", current_local=datetime(2026, 9, 3, 10, tzinfo=UTC)
        )
        db.commit()
    with Session(engine) as restarted:
        claim = notifications.claim_delivery(restarted, now=datetime(2026, 9, 3, 10))
        assert claim is not None
        notifications.complete_delivery(
            restarted,
            claim["delivery_id"],
            claim["claim_token"],
            delivered=True,
            now=datetime(2026, 9, 3, 10, 0, 1),
        )
    with Session(engine) as restarted_again:
        assert notifications.claim_delivery(restarted_again, now=datetime(2026, 9, 3, 11)) is None
        delivery = restarted_again.scalar(select(NotificationDelivery))
        assert delivery is not None and delivery.status == "DELIVERED"


def test_failed_delivery_retries_but_stale_sending_becomes_uncertain(monkeypatch) -> None:
    desktop(monkeypatch)
    db = make_session()
    enable(db)
    notice = add_notice(db)
    notifications.record_notice_event(
        db, notice, "NEW", current_local=datetime(2026, 9, 3, 10, tzinfo=UTC)
    )
    db.commit()
    first = notifications.claim_delivery(db, now=datetime(2026, 9, 3, 10))
    assert first is not None
    notifications.complete_delivery(
        db,
        first["delivery_id"],
        first["claim_token"],
        delivered=False,
        error="fixture rejection",
        now=datetime(2026, 9, 3, 10),
    )
    retry = notifications.claim_delivery(db, now=datetime(2026, 9, 3, 10, 3))
    assert retry is not None and retry["delivery_id"] == first["delivery_id"]
    assert notifications.claim_delivery(db, now=datetime(2026, 9, 3, 10, 10)) is None
    delivery = db.get(NotificationDelivery, first["delivery_id"])
    assert delivery is not None and delivery.status == "UNCERTAIN"
    db.close()


def test_quiet_hours_delay_claim(monkeypatch) -> None:
    desktop(monkeypatch)
    db = make_session()
    enable(db)
    notice = add_notice(db)
    local = datetime(2026, 9, 3, 23, 30, tzinfo=UTC)
    event = notifications.record_notice_event(db, notice, "NEW", current_local=local)[0]
    db.commit()
    assert event.available_at == datetime(2026, 9, 4, 8)
    assert notifications.claim_delivery(db, now=datetime(2026, 9, 4, 7, 59)) is None
    assert notifications.claim_delivery(db, now=datetime(2026, 9, 4, 8)) is not None
    db.close()


def test_source_health_severity_is_transition_based(monkeypatch) -> None:
    desktop(monkeypatch)
    db = make_session()
    enable(db)
    source = Source(
        code="fixture", name="MOCK / FIXTURE", base_url="https://example.test",
        health_state="cloud_unconfigured", last_error_code="PUBLIC_FEED_NOT_CONFIGURED",
        last_checked_at=datetime(2026, 9, 3, 1),
    )
    db.add(source)
    db.flush()
    info = notifications.record_source_health_transition(db, source, "unconfigured")
    duplicate_transition = notifications.record_source_health_transition(db, source, "cloud_unconfigured")
    assert info is not None and info.severity == "info"
    assert duplicate_transition is None
    source.health_state = "needs_reauth"
    source.last_error_code = "AUTH_EXPIRED"
    source.last_checked_at += timedelta(hours=1)
    warning = notifications.record_source_health_transition(db, source, "healthy")
    assert warning is not None and warning.event_type == "SOURCE_AUTH_REQUIRED"
    assert warning.severity == "warning"
    db.close()


def test_gate14_migration_from_050_is_additive(tmp_path) -> None:
    path = tmp_path / "gate14.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sources (id INTEGER PRIMARY KEY, code VARCHAR(40), name VARCHAR(200), base_url VARCHAR(500));
        CREATE TABLE notices (id INTEGER PRIMARY KEY, title VARCHAR(1000));
        CREATE TABLE user_states (id INTEGER PRIMARY KEY, notice_id INTEGER, is_read BOOLEAN, is_archived BOOLEAN, is_favorite BOOLEAN);
        CREATE TABLE schema_migrations (version VARCHAR(40) PRIMARY KEY, applied_at DATETIME);
        INSERT INTO notices VALUES (7, 'preserved fixture');
        INSERT INTO user_states VALUES (1, 7, 1, 0, 1);
        INSERT INTO schema_migrations VALUES ('13.0', '2026-09-02 00:00:00');
        """
    )
    connection.commit()
    connection.close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    run_gate14_migrations(engine)
    run_gate14_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"notification_events", "notification_deliveries", "notification_preferences"} <= tables
    with engine.connect() as db:
        assert db.exec_driver_sql("SELECT title FROM notices WHERE id=7").scalar_one() == "preserved fixture"
        assert tuple(db.exec_driver_sql("SELECT is_read, is_favorite FROM user_states WHERE notice_id=7").one()) == (1, 1)
        assert db.exec_driver_sql("SELECT COUNT(*) FROM notification_preferences").scalar_one() == 1
        versions = {row[0] for row in db.exec_driver_sql("SELECT version FROM schema_migrations")}
    assert versions == {"13.0", "14.0"}


def test_cloud_role_does_not_expose_personal_notification_api(monkeypatch) -> None:
    monkeypatch.setattr(
        notification_api,
        "get_settings",
        lambda: SimpleNamespace(effective_deployment_role="cloud"),
    )
    with pytest.raises(HTTPException) as error:
        notification_api.require_local_notifications()
    assert error.value.status_code == 404
