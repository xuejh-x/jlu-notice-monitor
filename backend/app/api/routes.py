from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from math import ceil
from typing import Any, Literal
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import DateTime, and_, case, cast, exists, func, or_, select
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.crawler import crawler_manager, scheduler_manager, startup_sync
from app import __version__
from app.config import get_settings, load_yaml
from app.crawler.runner import CrawlerAlreadyRunning
from app.database import get_db
from app.logging_config import _safe_value, log_event
from app.models import Favorite, Notice, NoticeSourceRelation, Source, UserState
from app.runtime import status as runtime_status
from app.services.dates import deadline_metadata
from app.sources.cloud import PUBLIC_FEED_NOT_CONFIGURED, is_public_feed_not_configured

api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _serialize_notice(notice: Notice, detailed: bool = False) -> dict[str, Any]:
    deadline_status, days = deadline_metadata(notice.registration_deadline)
    state = notice.user_state
    detected_at = notice.first_seen_at
    if notice.source.source_type == "single_page_monitor" and detected_at is not None and detected_at.tzinfo is None:
        # Stored timestamps are naive UTC, not local wall-clock time. Preserve
        # ordinary DTOs but let the single-page UI display the real instant.
        detected_at = detected_at.replace(tzinfo=UTC)
    result: dict[str, Any] = {
        "id": notice.id,
        "title": notice.title,
        "url": notice.url,
        "publish_date": notice.publish_date,
        "publisher": notice.publisher,
        "category": notice.category,
        "importance_score": notice.importance_score,
        "registration_start": notice.registration_start,
        "registration_deadline": notice.registration_deadline,
        "event_start": notice.event_start,
        "event_end": notice.event_end,
        "deadline_status": deadline_status,
        "days_until_deadline": days,
        "status": notice.status,
        "first_seen_at": detected_at,
        "last_seen_at": notice.last_seen_at,
        "updated_at": notice.updated_at,
        "is_read": state.is_read if state else False,
        "is_archived": state.is_archived if state else False,
        "is_favorite": state.is_favorite if state else False,
        "sources": [
            {
                "code": relation.source.code,
                "name": relation.source.name,
                "url": relation.source_url,
            }
            for relation in notice.source_relations
        ],
    }
    if detailed:
        result.update(
            {
                "content": notice.content,
                "target_students": notice.target_students,
                "registration_method": notice.registration_method,
                "competition_level": notice.competition_level,
                "attachments": [
                    {"filename": item.filename, "url": item.url, "type": item.type}
                    for item in notice.attachments
                ],
                "updates": [
                    {
                        "detected_at": item.detected_at,
                        "old_hash": item.old_hash,
                        "new_hash": item.new_hash,
                        "summary": item.summary,
                    }
                    for item in notice.updates
                ],
            }
        )
    return result


def _notice_options() -> tuple[Any, ...]:
    return (
        selectinload(Notice.source_relations).selectinload(NoticeSourceRelation.source),
        selectinload(Notice.attachments),
        selectinload(Notice.updates),
        selectinload(Notice.user_state),
    )


def _get_notice(db: Session, notice_id: int) -> Notice:
    notice = db.scalar(
        select(Notice)
        .where(Notice.id == notice_id, _visible_notice_condition())
        .options(*_notice_options())
    )
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    return notice


def _visible_notice_condition() -> Any:
    return exists(
        select(NoticeSourceRelation.id)
        .join(Source, Source.id == NoticeSourceRelation.source_id)
        .where(
            NoticeSourceRelation.notice_id == Notice.id,
            Source.is_deleted.is_(False),
            or_(
                Source.ownership.not_in(("OFFICIAL_CLOUD", "SHARED_CLOUD")),
                Source.subscribed.is_(True),
            ),
        )
    )


def _global_notice_counts(db: Session) -> tuple[int, int]:
    total = db.scalar(
        select(func.count(Notice.id)).where(_visible_notice_condition())
    ) or 0
    unread = db.scalar(
        select(func.count(Notice.id))
        .outerjoin(UserState, UserState.notice_id == Notice.id)
        .where(
            _visible_notice_condition(),
            or_(UserState.id.is_(None), UserState.is_read.is_(False)),
        )
    ) or 0
    return total, unread


def _single_page_notice_condition() -> Any:
    # Classify by the owning source, not by one hard-coded adapter code.
    return Notice.source.has(Source.source_type == "single_page_monitor")


def _notice_timezone() -> tuple[str, tzinfo]:
    name = str(load_yaml("settings.yaml").get("app", {}).get("timezone", "Asia/Shanghai"))
    try:
        return name, ZoneInfo(name)
    except ZoneInfoNotFoundError:
        # Windows packages may not have IANA data. These project/default zones
        # have fixed offsets for the contemporary detection timestamps.
        if name == "Asia/Shanghai":
            return name, timezone(timedelta(hours=8))
        if name == "UTC":
            return name, UTC
        raise


def _date_start_utc(value: date, zone: tzinfo) -> datetime:
    return datetime.combine(value, datetime.min.time(), zone).astimezone(UTC).replace(tzinfo=None)


def _latest_notice_ordering(db: Session) -> tuple[Any, ...]:
    name, zone = _notice_timezone()
    if db.get_bind().dialect.name == "sqlite":
        # SQLite has no IANA timezone conversion. A connection-local pure
        # function handles publication-day midnight (including DST) without
        # changing stored fields, the schema, or ordinary-source ordering.
        def publication_midnight(value: str | None) -> str | None:
            if value is None:
                return None
            return _date_start_utc(date.fromisoformat(value), zone).isoformat(" ", timespec="microseconds")

        connection = db.connection().connection.driver_connection
        connection.create_function("jlu_publication_midnight_utc", 1, publication_midnight, deterministic=True)
        published = func.jlu_publication_midnight_utc(Notice.publish_date)
    else:
        published = func.timezone("UTC", func.timezone(name, cast(Notice.publish_date, DateTime)))
    effective = case((_single_page_notice_condition(), Notice.first_seen_at), else_=published)
    return effective.desc().nullslast(), Notice.first_seen_at.desc()


@api_router.get("/notices")
def list_notices(
    category: str | None = None,
    source: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = Query(None, alias="status"),
    deadline_status: Literal["unknown", "expired", "today", "urgent", "normal", "active"] | None = None,
    favorite: bool | None = None,
    read_filter: bool | None = Query(None, alias="read"),
    q: str | None = Query(None, min_length=1),
    keyword: str | None = None,
    sort: Literal["newest", "priority", "deadline"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(Notice).options(*_notice_options())
    count_query = select(func.count(func.distinct(Notice.id)))
    conditions: list[Any] = [_visible_notice_condition()]
    if category:
        category_values = [value.strip() for value in category.split(",") if value.strip()]
        if category_values:
            conditions.append(Notice.category.in_(category_values))
    if min_score is not None:
        conditions.append(Notice.importance_score >= min_score)
    if date_from or date_to:
        monitor = _single_page_notice_condition()
        _, zone = _notice_timezone()
        if date_from:
            conditions.append(or_(
                and_(monitor, Notice.first_seen_at >= _date_start_utc(date_from, zone)),
                and_(~monitor, Notice.publish_date >= date_from),
            ))
        if date_to:
            # Inclusive calendar end, exclusive next local midnight. Do not
            # assume every local day is 24 hours or truncate sub-second times.
            end_condition = (Notice.first_seen_at < _date_start_utc(date_to + timedelta(days=1), zone)
                             if date_to < date.max else Notice.first_seen_at.is_not(None))
            conditions.append(or_(
                and_(monitor, end_condition),
                and_(~monitor, Notice.publish_date <= date_to),
            ))
    if status_filter:
        conditions.append(Notice.status == status_filter)
    if deadline_status:
        today = date.today()
        if deadline_status == "unknown":
            conditions.append(Notice.registration_deadline.is_(None))
        elif deadline_status == "expired":
            conditions.append(Notice.registration_deadline < today)
        elif deadline_status == "today":
            conditions.append(Notice.registration_deadline == today)
        elif deadline_status == "urgent":
            conditions.extend((
                Notice.registration_deadline > today,
                Notice.registration_deadline <= today + timedelta(days=3),
            ))
        elif deadline_status == "normal":
            conditions.append(Notice.registration_deadline > today + timedelta(days=3))
        else:
            conditions.append(Notice.registration_deadline >= today)
    search_value = q or keyword
    if search_value:
        value = f"%{search_value}%"
        conditions.append(or_(Notice.title.ilike(value), Notice.content.ilike(value)))
    if source:
        query = query.join(Notice.source_relations).join(Source)
        count_query = count_query.join(Notice.source_relations).join(Source)
        conditions.append(Source.code == source)
    if favorite is not None or read_filter is not None:
        query = query.outerjoin(UserState, UserState.notice_id == Notice.id)
        count_query = count_query.outerjoin(UserState, UserState.notice_id == Notice.id)
        user_state_joined = True
    else:
        user_state_joined = False
    if favorite is True:
        conditions.append(UserState.is_favorite.is_(True))
    elif favorite is False:
        conditions.append(or_(UserState.id.is_(None), UserState.is_favorite.is_(False)))
    if read_filter is True:
        conditions.append(UserState.is_read.is_(True))
    elif read_filter is False:
        conditions.append(or_(UserState.id.is_(None), UserState.is_read.is_(False)))
    if conditions:
        query = query.where(*conditions)
        count_query = count_query.where(*conditions)
    total_count = db.scalar(count_query) or 0
    unread_count_query = count_query
    if not user_state_joined:
        unread_count_query = unread_count_query.outerjoin(
            UserState, UserState.notice_id == Notice.id
        )
    unread_count = db.scalar(
        unread_count_query.where(
            or_(UserState.id.is_(None), UserState.is_read.is_(False))
        )
    ) or 0
    all_count, _ = _global_notice_counts(db)
    if sort == "priority":
        ordering = (Notice.importance_score.desc(), Notice.publish_date.desc().nullslast())
    elif sort == "deadline":
        ordering = (Notice.registration_deadline.asc().nullslast(), Notice.publish_date.desc().nullslast())
    else:
        ordering = _latest_notice_ordering(db)
    notices = db.scalars(
        query.order_by(*ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return {
        "items": [_serialize_notice(item) for item in notices],
        "total_count": total_count,
        "unread_count": unread_count,
        "all_count": all_count,
        # Compatibility alias for older clients. New clients use total_count.
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total_count / page_size) if total_count else 0,
    }


@api_router.get("/notices/today")
def notices_today(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    start = datetime.combine(date.today(), datetime.min.time())
    notices = db.scalars(
        select(Notice)
        .where(Notice.first_seen_at >= start, Notice.status != "baseline", _visible_notice_condition())
        .options(*_notice_options())
        .order_by(Notice.importance_score.desc())
    ).all()
    return [_serialize_notice(item) for item in notices]


@api_router.get("/notices/important")
def important_notices(min_score: int = Query(70, ge=0, le=100), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    notices = db.scalars(
        select(Notice)
        .where(Notice.importance_score >= min_score, _visible_notice_condition())
        .options(*_notice_options())
        .order_by(Notice.importance_score.desc())
    ).all()
    return [_serialize_notice(item) for item in notices]


@api_router.get("/notices/deadlines")
def deadline_notices(days: int = Query(30, ge=0, le=365), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    today = date.today()
    notices = db.scalars(
        select(Notice)
        .where(
            Notice.registration_deadline >= today,
            Notice.registration_deadline <= today + timedelta(days=days),
            _visible_notice_condition(),
        )
        .options(*_notice_options())
        .order_by(Notice.registration_deadline)
    ).all()
    return [_serialize_notice(item) for item in notices]


@api_router.get("/notices/{notice_id}")
def get_notice(notice_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _serialize_notice(_get_notice(db, notice_id), detailed=True)


@api_router.get("/categories")
def categories(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(Notice.category, func.count(Notice.id)).group_by(Notice.category)).all()
    return [{"category": category, "count": count} for category, count in rows]


@api_router.get("/sources")
def sources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Source).where(Source.is_deleted.is_(False)).order_by(Source.id)).all()
    results: list[dict[str, Any]] = []
    for item in rows:
        private_oa = item.code == "oa" and item.ownership == "CUSTOM_LOCAL_PRIVATE"
        public_feed_missing = item.ownership in {"OFFICIAL_CLOUD", "SHARED_CLOUD"} and is_public_feed_not_configured(
            item.last_error_code,
            item.last_error,
        )
        projected_health_state = "cloud_unconfigured" if public_feed_missing else item.health_state
        if item.ownership in {"OFFICIAL_CLOUD", "SHARED_CLOUD"} and not item.subscribed:
            source_status = "disabled"
            message = "当前设备未订阅此官方来源"
        elif item.health_state == "needs_reauth" or item.last_error == "OA_LOGIN_EXPIRED":
            source_status = "needs_reauth"
            message = "登录状态已失效，请在来源页面重新登录"
        elif private_oa and item.health_state == "unconfigured":
            source_status = "login_required"
            message = "需要完成首次登录配置"
        elif not item.enabled:
            source_status = "disabled"
            message = "尚未完成首次登录配置" if private_oa else "数据源已禁用"
        elif public_feed_missing:
            source_status = "cloud_unconfigured"
            message = "等待 Notice Hub 公共源启用"
        elif item.health_state in {"auth_error", "parse_error", "network_error", "source_error", "unsupported", "syncing"}:
            source_status = item.health_state
            message = item.last_error
        elif item.last_error:
            source_status = "unavailable"
            message = item.last_error
        elif item.last_success_at:
            source_status = "healthy"
            message = None
        elif private_oa:
            source_status = "login_required"
            message = "需要先执行 oa-login"
        else:
            source_status = "unconfigured"
            message = "尚未执行首次抓取"
        results.append({
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "base_url": item.base_url,
            "enabled": item.enabled,
            "subscribed": item.subscribed,
            "ownership": item.ownership,
            "source_type": item.source_type,
            "auth_type": item.auth_type,
            "auth_required": item.auth_type != "none",
            "health_state": projected_health_state,
            "source_scope": item.source_scope,
            "execution": item.execution,
            "execution_policy": item.execution_policy,
            "cloud_policy": item.cloud_policy,
            "cloud_source_id": item.cloud_source_id,
            "last_checked_at": item.last_checked_at,
            "last_success_at": item.last_success_at,
            "last_error": None if public_feed_missing else item.last_error,
            "last_error_code": PUBLIC_FEED_NOT_CONFIGURED if public_feed_missing else item.last_error_code,
            "consecutive_errors": item.consecutive_errors,
            "status": source_status,
            "message": message,
            "notice_count": db.scalar(
                select(func.count(func.distinct(NoticeSourceRelation.notice_id))).where(
                    NoticeSourceRelation.source_id == item.id
                )
            ) or 0,
        })
    return results


def health_status(db: Session) -> dict[str, Any] | JSONResponse:
    payload: dict[str, Any] = {
        "status": "ok",
        "service": "jlu-notice-monitor",
        "version": __version__,
        "database": "ok",
        "crawler": "running" if crawler_manager.running else "idle",
        "scheduler": "running" if scheduler_manager.running else "idle",
        "initialized": runtime_status()["initialized"],
        "environment": get_settings().environment,
    }
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database health check failed")
        payload.update(status="degraded", database="error")
        return JSONResponse(status_code=503, content=payload)
    return payload


@api_router.get("/health", response_model=None)
def api_health(db: Session = Depends(get_db)) -> dict[str, Any] | JSONResponse:
    return health_status(db)


@api_router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict[str, int]:
    total, unread = _global_notice_counts(db)
    return {
        "notices": total,
        "sources": db.scalar(select(func.count(Source.id))) or 0,
        "unread": unread,
        "favorites": db.scalar(select(func.count(UserState.id)).where(UserState.is_favorite.is_(True))) or 0,
    }


@api_router.get("/search")
def search(
    keyword: str = Query(min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return list_notices(
        category=None,
        source=None,
        min_score=None,
        date_from=None,
        date_to=None,
        status_filter=None,
        deadline_status=None,
        favorite=None,
        read_filter=None,
        q=keyword,
        keyword=keyword,
        sort="newest",
        page=page,
        page_size=page_size,
        db=db,
    )


@api_router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    urgent_end = today + timedelta(days=3)
    recent = db.scalars(
        select(Notice)
        .where(_visible_notice_condition())
        .options(*_notice_options())
        .order_by(*_latest_notice_ordering(db))
        .limit(10)
    ).all()
    total_count, unread_count = _global_notice_counts(db)
    return {
        "total_count": total_count,
        "new_today": db.scalar(
            select(func.count(Notice.id)).where(
                Notice.first_seen_at >= start, Notice.status != "baseline", _visible_notice_condition()
            )
        ) or 0,
        "urgent": db.scalar(
            select(func.count(Notice.id)).where(
                Notice.registration_deadline >= today,
                Notice.registration_deadline <= urgent_end,
                _visible_notice_condition(),
            )
        ) or 0,
        "important": db.scalar(select(func.count(Notice.id)).where(Notice.importance_score >= 70, _visible_notice_condition())) or 0,
        "upcoming_deadlines": db.scalar(
            select(func.count(Notice.id)).where(Notice.registration_deadline >= today, _visible_notice_condition())
        ) or 0,
        "unread": unread_count,
        "source_status": sources(db),
        "recent_notices": [_serialize_notice(item) for item in recent],
    }


def _set_state(db: Session, notice_id: int, field: str, value: bool) -> dict[str, Any]:
    notice = _get_notice(db, notice_id)
    state_row = notice.user_state or UserState(notice_id=notice.id)
    setattr(state_row, field, value)
    db.add(state_row)
    if field == "is_favorite":
        favorite = db.scalar(select(Favorite).where(Favorite.notice_id == notice.id))
        if value and favorite is None:
            db.add(Favorite(notice_id=notice.id))
        elif not value and favorite:
            db.delete(favorite)
    db.commit()
    return {"notice_id": notice_id, field: value}


@api_router.post("/notices/read-all")
def mark_all_read(db: Session = Depends(get_db)) -> dict[str, int]:
    """Mark every visible unread notice read; repeated requests are no-ops."""
    notices = db.scalars(
        select(Notice)
        .where(_visible_notice_condition())
        .options(selectinload(Notice.user_state))
    ).all()
    updated = 0
    for notice in notices:
        state = notice.user_state
        if state is None:
            db.add(UserState(notice_id=notice.id, is_read=True))
            updated += 1
        elif not state.is_read:
            state.is_read = True
            updated += 1
    db.commit()
    return {"updated": updated}


@api_router.post("/notices/{notice_id}/read")
def mark_read(notice_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_state(db, notice_id, "is_read", True)


@api_router.post("/notices/{notice_id}/unread")
def mark_unread(notice_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_state(db, notice_id, "is_read", False)


@api_router.post("/notices/{notice_id}/favorite")
def favorite(notice_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_state(db, notice_id, "is_favorite", True)


@api_router.post("/notices/{notice_id}/unfavorite")
def unfavorite(notice_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_state(db, notice_id, "is_favorite", False)


@api_router.post("/notices/{notice_id}/archive")
def archive(notice_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_state(db, notice_id, "is_archived", True)


@api_router.post("/notices/{notice_id}/unarchive")
def unarchive(notice_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_state(db, notice_id, "is_archived", False)


@api_router.post("/crawler/run", status_code=status.HTTP_202_ACCEPTED)
async def run_crawler() -> dict[str, str]:
    try:
        crawler_manager.start()
    except CrawlerAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    log_event(logger, logging.INFO, "manual_crawler_requested", trigger_source="manual")
    return {"status": "started"}


@api_router.post("/crawler/run/{source_code}", status_code=status.HTTP_202_ACCEPTED)
async def run_source(source_code: str) -> dict[str, str]:
    try:
        crawler_manager.start(source_code)
    except CrawlerAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "started", "source": source_code}


@api_router.get("/crawler/status")
def crawler_status() -> dict[str, Any]:
    return {
        **crawler_manager.status(),
        "scheduler": scheduler_manager.status(),
        "startup_sync": startup_sync.status(),
    }


@api_router.get("/runtime/diagnostics")
def runtime_diagnostics(db: Session = Depends(get_db)) -> dict[str, Any]:
    source_rows = db.scalars(select(Source).order_by(Source.code)).all()
    source_summary = [
        {
            "code": source.code,
            "enabled": source.enabled,
            "last_success_at": source.last_success_at,
            "last_error_at": source.last_checked_at if source.last_error else None,
            "last_error": _safe_value(source.last_error or ""),
            "consecutive_errors": source.consecutive_errors,
        }
        for source in source_rows
    ]
    failed = [item for item in source_summary if item["last_error"]]
    return {
        "service": "jlu-notice-monitor",
        "version": __version__,
        "runtime": runtime_status(),
        "database": {"status": "ok", "storage": "configured"},
        "crawler": crawler_manager.status(),
        "scheduler": scheduler_manager.status(),
        "sources": source_summary,
        "latest_error_summary": failed[0] if failed else None,
    }
