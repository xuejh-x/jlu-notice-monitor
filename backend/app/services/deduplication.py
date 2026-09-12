from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notice, NoticeSourceRelation


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def find_duplicate(
    db: Session,
    normalized_title: str,
    canonical_url: str,
    publish_date: date | None,
    source_id: int | None = None,
    public_id: str | None = None,
) -> Notice | None:
    if public_id:
        remote = db.scalar(select(Notice).where(Notice.public_id == public_id))
        if remote:
            return remote
    direct = db.scalar(select(Notice).where(Notice.canonical_url == canonical_url))
    if direct:
        return direct
    if normalized_title:
        exact_query = select(Notice).where(Notice.normalized_title == normalized_title)
        if source_id is not None:
            exact_query = exact_query.where(
                Notice.source_relations.any(NoticeSourceRelation.source_id == source_id)
            )
        exact_matches = db.scalars(exact_query).all()
        for exact in exact_matches:
            if publish_date and exact.publish_date:
                if abs((publish_date - exact.publish_date).days) <= 14:
                    return exact
            else:
                return exact
    candidate_query = select(Notice)
    if source_id is not None:
        candidate_query = candidate_query.where(
            Notice.source_relations.any(NoticeSourceRelation.source_id == source_id)
        )
    candidates = db.scalars(candidate_query.order_by(Notice.id.desc()).limit(300)).all()
    for candidate in candidates:
        if publish_date and candidate.publish_date:
            if abs((publish_date - candidate.publish_date).days) > 14:
                continue
        if len(normalized_title) >= 6 and title_similarity(normalized_title, candidate.normalized_title) >= 0.92:
            return candidate
    return None
