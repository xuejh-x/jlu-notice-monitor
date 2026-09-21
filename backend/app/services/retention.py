from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import AppState, Favorite, Notice, NotificationEvent, UserState


LAST_CLEANUP_KEY = "storage_retention_last_cleanup_at"


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class CleanupResult:
    deleted_count: int
    cleanup_at: datetime


def _cutoff(settings: Settings, now: datetime) -> date:
    return (now - timedelta(days=settings.retention_days)).date()


def _is_local(settings: Settings) -> bool:
    return settings.effective_deployment_role != "cloud"


def cleanup_candidate_condition(settings: Settings, now: datetime) -> Any:
    """Return the shared selection predicate without issuing a destructive query."""

    cutoff = _cutoff(settings, now)
    old_notice = or_(
        Notice.publish_date < cutoff,
        (Notice.publish_date.is_(None) & (Notice.first_seen_at < datetime.combine(cutoff, datetime.min.time()))),
    )
    if not _is_local(settings):
        return old_notice
    return old_notice & ~or_(
        UserState.id.is_(None),
        UserState.is_read.is_(False),
        UserState.is_favorite.is_(True),
        Favorite.id.is_not(None),
        Notice.importance_score >= settings.retention_high_importance_score,
    )


def candidate_notice_ids(db: Session, settings: Settings, now: datetime) -> list[int]:
    query = select(Notice.id)
    if _is_local(settings):
        query = query.outerjoin(UserState, UserState.notice_id == Notice.id).outerjoin(
            Favorite, Favorite.notice_id == Notice.id
        )
    return list(db.scalars(query.where(cleanup_candidate_condition(settings, now))))


def _set_last_cleanup(db: Session, cleanup_at: datetime) -> None:
    state = db.get(AppState, LAST_CLEANUP_KEY)
    value = cleanup_at.replace(tzinfo=UTC).isoformat()
    if state is None:
        db.add(AppState(key=LAST_CLEANUP_KEY, value=value))
    else:
        state.value = value


def cleanup_notices(db: Session, settings: Settings | None = None, *, now: datetime | None = None) -> CleanupResult:
    """Delete notices selected by the retention policy and their dependent records.

    Notification events are explicitly removed before notices, so their delivery
    rows are removed through the existing event->delivery cascade instead of
    retaining orphaned reminders. Notice-owned metadata uses existing FKs.
    """

    configured = settings or get_settings()
    cleanup_at = now or utcnow()
    ids = candidate_notice_ids(db, configured, cleanup_at)
    if ids:
        if _is_local(configured):
            db.execute(delete(NotificationEvent).where(NotificationEvent.notice_id.in_(ids)))
            db.execute(delete(Favorite).where(Favorite.notice_id.in_(ids)))
            notices = db.scalars(select(Notice).where(Notice.id.in_(ids))).all()
            for notice in notices:
                db.delete(notice)
        else:
            # Cloud has no client-state tables; database cascades remove only
            # public notice-owned facts without loading Desktop relationships.
            db.execute(delete(Notice).where(Notice.id.in_(ids)))
    _set_last_cleanup(db, cleanup_at)
    return CleanupResult(deleted_count=len(ids), cleanup_at=cleanup_at)


def _parse_last_cleanup(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def run_scheduled_cleanup(settings: Settings | None = None, *, now: datetime | None = None) -> CleanupResult | None:
    """Run at most once during the configured interval; safe for every scheduler tick."""

    configured = settings or get_settings()
    cleanup_at = now or utcnow()
    with SessionLocal() as db:
        last = db.get(AppState, LAST_CLEANUP_KEY)
        last_at = _parse_last_cleanup(last.value if last else None)
        if last_at and cleanup_at - last_at < timedelta(hours=configured.retention_cleanup_interval_hours):
            return None
        result = cleanup_notices(db, configured, now=cleanup_at)
        db.commit()
        return result


def database_size_bytes(db: Session) -> int:
    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        page_count = db.scalar(text("PRAGMA page_count")) or 0
        page_size = db.scalar(text("PRAGMA page_size")) or 0
        return int(page_count) * int(page_size)
    if bind.dialect.name == "postgresql":
        return int(db.scalar(text("SELECT pg_database_size(current_database())")) or 0)
    return 0


def format_database_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def storage_status(db: Session, settings: Settings | None = None, *, now: datetime | None = None) -> dict[str, object]:
    configured = settings or get_settings()
    checked_at = now or utcnow()
    last = db.get(AppState, LAST_CLEANUP_KEY)
    total = db.scalar(select(func.count(Notice.id))) or 0
    candidates = len(candidate_notice_ids(db, configured, checked_at))
    size = database_size_bytes(db)
    return {
        "database_size": format_database_size(size),
        "database_size_bytes": size,
        "total_notifications": total,
        "cleanup_candidates": candidates,
        "last_cleanup_at": last.value if last else None,
        "retention_days": configured.retention_days,
        "preserves_local_exceptions": _is_local(configured),
    }
