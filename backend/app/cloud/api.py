from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.models import Notice, Source


router = APIRouter(prefix="/api")


def get_cloud_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def public_source_condition():
    return (
        Source.ownership.in_(("OFFICIAL_CLOUD", "SHARED_CLOUD"))
        & Source.is_deleted.is_(False)
    )


def serialize_attachment(item) -> dict[str, Any]:
    return {
        "id": item.id,
        "filename": item.filename,
        "url": item.url,
        "hash": item.content_hash,
        "created_at": item.created_at,
    }


def serialize_notice(notice: Notice, *, detailed: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": notice.id,
        "source_id": notice.source_id,
        "title": notice.title,
        "url": notice.url,
        "importance": notice.importance_score,
        "deadline": notice.registration_deadline,
        "published_at": notice.publish_date,
        "created_at": notice.first_seen_at,
        "updated_at": notice.updated_at,
        "version": notice.version,
        "content_hash": notice.content_hash,
    }
    if detailed:
        result["content"] = notice.content
        result["attachments"] = [serialize_attachment(item) for item in notice.attachments]
    return result


@router.get("/notices")
def list_notices(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    source: str | None = None,
    importance: int | None = Query(None, ge=0, le=100),
    keyword: str | None = Query(None, min_length=1, max_length=200),
    db: Session = Depends(get_cloud_db),
) -> dict[str, Any]:
    conditions = [public_source_condition()]
    if source:
        conditions.append(Source.id == int(source) if source.isdigit() else Source.code == source)
    if importance is not None:
        conditions.append(Notice.importance_score >= importance)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        conditions.append(or_(Notice.title.ilike(pattern), Notice.content.ilike(pattern)))
    base = select(Notice).join(Source, Source.id == Notice.source_id).where(*conditions)
    total = db.scalar(
        select(func.count(Notice.id)).join(Source, Source.id == Notice.source_id).where(*conditions)
    ) or 0
    rows = db.scalars(
        base.order_by(Notice.publish_date.desc().nullslast(), Notice.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return {
        "items": [serialize_notice(item) for item in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": ceil(total / limit) if total else 0,
    }


@router.get("/notices/{notice_id}")
def notice_detail(notice_id: int, db: Session = Depends(get_cloud_db)) -> dict[str, Any]:
    notice = db.scalar(
        select(Notice)
        .join(Source, Source.id == Notice.source_id)
        .where(Notice.id == notice_id, public_source_condition())
        .options(selectinload(Notice.attachments))
    )
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    return serialize_notice(notice, detailed=True)


@router.get("/sources")
def list_sources(db: Session = Depends(get_cloud_db)) -> dict[str, Any]:
    rows = db.scalars(select(Source).where(public_source_condition()).order_by(Source.name)).all()
    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "url": item.base_url,
                "type": item.source_type,
                "status": item.health_state,
                "last_success_time": item.last_success_at,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in rows
        ]
    }
