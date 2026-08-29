from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notice


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def find_duplicate(
    db: Session,
    normalized_title: str,
    canonical_url: str,
    publish_date: date | None,
) -> Notice | None:
    direct = db.scalar(select(Notice).where(Notice.canonical_url == canonical_url))
    if direct:
        return direct
    if normalized_title:
        exact_matches = db.scalars(
            select(Notice).where(Notice.normalized_title == normalized_title)
        ).all()
        for exact in exact_matches:
            if publish_date and exact.publish_date:
                if abs((publish_date - exact.publish_date).days) <= 14:
                    return exact
            else:
                return exact
    candidates = db.scalars(select(Notice).order_by(Notice.id.desc()).limit(300)).all()
    for candidate in candidates:
        if publish_date and candidate.publish_date:
            if abs((publish_date - candidate.publish_date).days) > 14:
                continue
        if len(normalized_title) >= 6 and title_similarity(normalized_title, candidate.normalized_title) >= 0.92:
            return candidate
    return None
