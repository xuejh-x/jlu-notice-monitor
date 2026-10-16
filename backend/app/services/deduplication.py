from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notice, NoticeSourceRelation


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _different_explicit_series(left: str, right: str) -> bool:
    # Similar headings may describe distinct rounds/editions. URL/native
    # identity still wins; this guard applies only to title-based matching.
    pattern = r"[（(]\s*([一二三四五六七八九十百零〇两\d]+)\s*[）)]|第\s*([一二三四五六七八九十百零〇两\d]+)\s*(期|批|届|次|轮|场)"
    first, second = re.findall(pattern, left), re.findall(pattern, right)
    return bool((first or second) and first != second)


def _different_explicit_admission_stage(left: str, right: str) -> bool:
    # Interview eligibility and provisional admission are distinct notices,
    # even when a long shared institution/program prefix dominates similarity.
    first = set(re.findall(r"复试名单|拟录取名单", left))
    second = set(re.findall(r"复试名单|拟录取名单", right))
    return bool(first and second and first.isdisjoint(second))


def _different_explicit_award(left: str, right: str) -> bool:
    # High title similarity does not make two named scholarship programs one
    # notice. Keep URL/public identity precedence and the existing threshold.
    pattern = r"(?:国家励志|国家|学业)奖学金"
    first, second = set(re.findall(pattern, left)), set(re.findall(pattern, right))
    return bool(first and second and first.isdisjoint(second))


def find_duplicate(
    db: Session,
    normalized_title: str,
    canonical_url: str,
    publish_date: date | None,
    source_id: int | None = None,
    public_id: str | None = None,
    title: str | None = None,
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
            if title and (_different_explicit_series(title, exact.title) or _different_explicit_award(title, exact.title) or _different_explicit_admission_stage(title, exact.title)):
                continue
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
        if title and (_different_explicit_series(title, candidate.title) or _different_explicit_award(title, candidate.title) or _different_explicit_admission_stage(title, candidate.title)):
            continue
        if publish_date and candidate.publish_date:
            if abs((publish_date - candidate.publish_date).days) > 14:
                continue
        if len(normalized_title) >= 6 and title_similarity(normalized_title, candidate.normalized_title) >= 0.92:
            return candidate
    return None
