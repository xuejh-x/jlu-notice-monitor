from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.crawler import crawler_manager
from app.crawler.runner import CrawlerAlreadyRunning
from app.database import get_db
from app.models import Favorite, Notice, NoticeSourceRelation, Source, UserState
from app.services.dates import deadline_metadata

api_router = APIRouter(prefix="/api")


def _serialize_notice(notice: Notice, detailed: bool = False) -> dict[str, Any]:
    deadline_status, days = deadline_metadata(notice.registration_deadline)
    state = notice.user_state
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
        "first_seen_at": notice.first_seen_at,
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
    notice = db.scalar(select(Notice).where(Notice.id == notice_id).options(*_notice_options()))
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    return notice


@api_router.get("/notices")
def list_notices(
    category: str | None = None,
    source: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = Query(None, alias="status"),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(Notice).options(*_notice_options())
    count_query = select(func.count(func.distinct(Notice.id)))
    conditions: list[Any] = []
    if category:
        conditions.append(Notice.category == category)
    if min_score is not None:
        conditions.append(Notice.importance_score >= min_score)
    if date_from:
        conditions.append(Notice.publish_date >= date_from)
    if date_to:
        conditions.append(Notice.publish_date <= date_to)
    if status_filter:
        conditions.append(Notice.status == status_filter)
    if keyword:
        value = f"%{keyword}%"
        conditions.append(or_(Notice.title.ilike(value), Notice.content.ilike(value)))
    if source:
        query = query.join(Notice.source_relations).join(Source)
        count_query = count_query.join(Notice.source_relations).join(Source)
        conditions.append(Source.code == source)
    if conditions:
        query = query.where(*conditions)
        count_query = count_query.where(*conditions)
    total = db.scalar(count_query) or 0
    notices = db.scalars(
        query.order_by(Notice.publish_date.desc().nullslast(), Notice.first_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return {
        "items": [_serialize_notice(item) for item in notices],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@api_router.get("/notices/today")
def notices_today(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    start = datetime.combine(date.today(), datetime.min.time())
    notices = db.scalars(
        select(Notice)
        .where(Notice.first_seen_at >= start, Notice.status != "baseline")
        .options(*_notice_options())
        .order_by(Notice.importance_score.desc())
    ).all()
    return [_serialize_notice(item) for item in notices]


@api_router.get("/notices/important")
def important_notices(min_score: int = Query(70, ge=0, le=100), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    notices = db.scalars(
        select(Notice)
        .where(Notice.importance_score >= min_score)
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
    rows = db.scalars(select(Source).order_by(Source.id)).all()
    results: list[dict[str, Any]] = []
    for item in rows:
        if not item.enabled:
            source_status = "disabled"
            message = "尚未完成首次登录配置" if item.code == "oa" else "数据源已禁用"
        elif item.last_error == "OA_LOGIN_EXPIRED":
            source_status = "login_expired"
            message = "登录状态已失效，请重新执行 oa-login"
        elif item.last_error:
            source_status = "unavailable"
            message = item.last_error
        elif item.last_success_at:
            source_status = "healthy"
            message = None
        elif item.code == "oa":
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
            "last_checked_at": item.last_checked_at,
            "last_success_at": item.last_success_at,
            "last_error": item.last_error,
            "consecutive_errors": item.consecutive_errors,
            "status": source_status,
            "message": message,
        })
    return results


@api_router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "notices": db.scalar(select(func.count(Notice.id))) or 0,
        "sources": db.scalar(select(func.count(Source.id))) or 0,
        "unread": db.scalar(select(func.count(UserState.id)).where(UserState.is_read.is_(False))) or 0,
        "favorites": db.scalar(select(func.count(UserState.id)).where(UserState.is_favorite.is_(True))) or 0,
    }


@api_router.get("/search")
def search(keyword: str = Query(min_length=1), page: int = 1, page_size: int = 20, db: Session = Depends(get_db)) -> dict[str, Any]:
    return list_notices(
        category=None,
        source=None,
        min_score=None,
        date_from=None,
        date_to=None,
        status_filter=None,
        keyword=keyword,
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
        .options(*_notice_options())
        .order_by(Notice.publish_date.desc().nullslast(), Notice.first_seen_at.desc())
        .limit(10)
    ).all()
    return {
        "new_today": db.scalar(
            select(func.count(Notice.id)).where(
                Notice.first_seen_at >= start, Notice.status != "baseline"
            )
        ) or 0,
        "urgent": db.scalar(
            select(func.count(Notice.id)).where(
                Notice.registration_deadline >= today,
                Notice.registration_deadline <= urgent_end,
            )
        ) or 0,
        "important": db.scalar(select(func.count(Notice.id)).where(Notice.importance_score >= 70)) or 0,
        "upcoming_deadlines": db.scalar(
            select(func.count(Notice.id)).where(Notice.registration_deadline >= today)
        ) or 0,
        "unread": db.scalar(select(func.count(UserState.id)).where(UserState.is_read.is_(False))) or 0,
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
    return crawler_manager.status()
