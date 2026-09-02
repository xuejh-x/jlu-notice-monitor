from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from hashlib import sha256
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Notice, NoticeSourceRelation, Source

router = APIRouter(prefix="/public/v1", tags=["public-feed"])
_requests: dict[str, deque[datetime]] = defaultdict(deque)
_rate_lock = Lock()


def public_rate_limit(request: Request) -> None:
    address = request.client.host if request.client else "unknown"
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=1)
    with _rate_lock:
        bucket = _requests[address]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= 120:
            raise HTTPException(status_code=429, detail="Public feed rate limit exceeded")
        bucket.append(now)


def _public_id(source_code: str, canonical_url: str) -> str:
    return sha256(f"{source_code}|{canonical_url}".encode("utf-8")).hexdigest()


@router.get("/sources", dependencies=[Depends(public_rate_limit)])
def public_sources(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(
        select(Source)
        .where(
            Source.ownership.in_(("OFFICIAL_CLOUD", "SHARED_CLOUD")),
        )
        .order_by(Source.code)
    ).all()
    return {
        "version": "1",
        "items": [
            {
                "id": source.code,
                "code": source.code,
                "name": source.name,
                "base_url": source.base_url,
                "source_identity": source.source_identity,
                "source_scope": source.source_scope,
                "cloud_policy": source.cloud_policy,
            }
            for source in rows
        ],
    }


@router.get("/notices", dependencies=[Depends(public_rate_limit)])
def public_notices(
    source: str | None = None,
    updated_after: datetime | None = None,
    after_id: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = (
        select(NoticeSourceRelation)
        .join(NoticeSourceRelation.source)
        .join(NoticeSourceRelation.notice)
        .where(
            Source.ownership.in_(("OFFICIAL_CLOUD", "SHARED_CLOUD")),
            Source.cloud_policy != "force_disabled",
        )
        .options(
            selectinload(NoticeSourceRelation.source),
            selectinload(NoticeSourceRelation.notice).selectinload(Notice.attachments),
        )
    )
    if source:
        query = query.where(Source.code == source)
    if updated_after is not None:
        query = query.where(
            or_(
                Notice.updated_at > updated_after,
                and_(Notice.updated_at == updated_after, NoticeSourceRelation.id > after_id),
            )
        )
    rows = db.scalars(query.order_by(Notice.updated_at, NoticeSourceRelation.id).limit(page_size + 1)).all()
    page = rows[:page_size]
    items = []
    for relation in page:
        notice = relation.notice
        items.append(
            {
                "public_id": _public_id(relation.source.code, notice.canonical_url),
                "source": {
                    "id": relation.source.code,
                    "code": relation.source.code,
                    "name": relation.source.name,
                    "base_url": relation.source.base_url,
                },
                "title": notice.title,
                "content": notice.content,
                "url": relation.source_url,
                "canonical_url": notice.canonical_url,
                "publish_date": notice.publish_date,
                "publisher": notice.publisher,
                "category": notice.category,
                "registration_start": notice.registration_start,
                "registration_deadline": notice.registration_deadline,
                "event_start": notice.event_start,
                "event_end": notice.event_end,
                "target_students": notice.target_students,
                "registration_method": notice.registration_method,
                "competition_level": notice.competition_level,
                "content_hash": relation.content_hash,
                "updated_at": notice.updated_at,
                "attachments": [
                    {"filename": attachment.filename, "url": attachment.url, "type": attachment.type}
                    for attachment in notice.attachments
                ],
            }
        )
    last_relation = page[-1] if page else None
    return {
        "version": "1",
        "items": items,
        "has_more": len(rows) > page_size,
        "next": {
            "updated_after": last_relation.notice.updated_at,
            "after_id": last_relation.id,
        } if last_relation else None,
    }
