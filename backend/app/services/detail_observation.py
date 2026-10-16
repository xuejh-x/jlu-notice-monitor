"""Transactional detail checkpoints and source-owned attachment references.

Uses the existing AppState table; never commits on behalf of the caller.
Legacy attachment rows without provenance are deliberately retained.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppState, Attachment, Notice, NoticeSourceRelation, Source
from app.schemas.notice import NoticeCandidate
from app.services.normalization import content_hash


def observation_key(notice_id: int) -> str:
    return f"detail-observation:{notice_id}"


def relation_key(source_id: int, item_key: str) -> str:
    return sha256(json.dumps([source_id, item_key]).encode()).hexdigest()


def _fingerprint(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _identity(notice: Notice) -> list[str]:
    # SQLite may reuse a deleted row id. Do not inherit its old checkpoint.
    return [notice.first_seen_at.isoformat(), notice.canonical_url]


def _files_valid(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(url, str) and isinstance(item, dict)
        and set(item) == {"filename", "type"}
        and all(isinstance(v, str) for v in item.values())
        for url, item in value.items()
    )


def load_observation(db: Session, notice: Notice, *, for_update: bool = False) -> dict[str, Any] | None:
    row = db.get(AppState, observation_key(notice.id), with_for_update=for_update, populate_existing=for_update)
    if row is None:
        return None
    try:
        value = json.loads(row.value)
        if (value["schema"] != 1 or value["identity"] != _identity(notice)
                or not _files_valid(value["legacy"]) or not isinstance(value["relations"], dict)):
            return None
        for record in value["relations"].values():
            if (not isinstance(record, dict) or not isinstance(record["source_id"], int)
                    or not isinstance(record["source_url"], str) or not _files_valid(record["attachments"])):
                return None
            for field in ("checked_at", "attempted_at"):
                if record.get(field) is not None:
                    parsed = datetime.fromisoformat(record[field])
                    if parsed.tzinfo is not None:
                        return None
        return value
    except (ValueError, TypeError, KeyError, AttributeError):
        # Corrupt/unknown checkpoints must not authorize deletion or skipping.
        return None


def _initial(db: Session, notice: Notice) -> dict[str, Any]:
    return {
        "schema": 1, "identity": _identity(notice), "relations": {},
        "legacy": {a.url: {"filename": a.filename, "type": a.type}
                   for a in db.scalars(select(Attachment).where(Attachment.notice_id == notice.id))},
    }


def _save(db: Session, notice: Notice, value: dict[str, Any]) -> None:
    row = db.get(AppState, observation_key(notice.id))
    if row is None:
        row = AppState(key=observation_key(notice.id))
        db.add(row)
    row.value = json.dumps(value, sort_keys=True, ensure_ascii=False)


def recheck_priority(db: Session, relation: NoticeSourceRelation, now: datetime, interval: int) -> datetime | None:
    value = load_observation(db, relation.notice)
    record = (value or {}).get("relations", {}).get(relation_key(relation.source_id, relation.origin_item_key or ""), {})
    checked = datetime.fromisoformat(record["checked_at"]) if record.get("checked_at") else None
    if checked is not None and now - checked < timedelta(seconds=interval):
        return None
    # A failed attempt does not establish success, but moves behind other due
    # items so a broken detail cannot monopolize every bounded run.
    return datetime.fromisoformat(record["attempted_at"]) if record.get("attempted_at") else datetime.min


def mark_recheck_attempt(db: Session, relation: NoticeSourceRelation, now: datetime) -> None:
    value = load_observation(db, relation.notice, for_update=True) or _initial(db, relation.notice)
    key = relation_key(relation.source_id, relation.origin_item_key or "")
    record = value["relations"].setdefault(key, {
        "source_id": relation.source_id, "source_url": relation.source_url, "attachments": {},
    })
    record["attempted_at"] = now.isoformat()
    _save(db, relation.notice, value)


def observe_detail(
    db: Session, notice: Notice, source: Source, item_key: str, candidate: NoticeCandidate, now: datetime,
    *, previous_item_key: str | None = None,
) -> tuple[bool, str, str]:
    value = load_observation(db, notice, for_update=True) or _initial(db, notice)
    records = value["relations"]
    key = relation_key(source.id, item_key)
    # The same DB relation can acquire an origin key when switching between a
    # legacy local adapter and a public feed. Move its ownership, do not leave
    # an imaginary second contributor retaining every old attachment forever.
    if previous_item_key is not None:
        old_key = relation_key(source.id, previous_item_key)
        if old_key != key and old_key in records and key not in records:
            records[key] = records.pop(old_key)
    previous = records.get(key)
    old_files = previous["attachments"] if previous else {}
    incoming = {a.url: {"filename": a.filename, "type": a.type} for a in candidate.attachments}
    files = incoming if candidate.attachments_complete else old_files | incoming
    old_owned = {url for record in records.values() for url in record["attachments"]}
    records[key] = {
        "source_id": source.id, "source_url": candidate.url, "attachments": files,
        "checked_at": now.isoformat(), "attempted_at": now.isoformat(),
    }
    # A stable display choice for URLs contributed by multiple relations.
    ordered = sorted(records.items(), key=lambda pair: (
        not (pair[1]["source_id"] == notice.source_id and pair[1]["source_url"] == notice.url), pair[0],
    ))
    desired: dict[str, Any] = {}
    for _, record in ordered:
        for url, metadata in record["attachments"].items():
            desired.setdefault(url, metadata)
    for url, metadata in value["legacy"].items():
        desired.setdefault(url, metadata)
    existing = {a.url: a for a in db.scalars(select(Attachment).where(Attachment.notice_id == notice.id))}
    public_changed = False
    for url, metadata in desired.items():
        attachment = existing.get(url)
        if attachment is None:
            db.add(Attachment(notice_id=notice.id, url=url, **metadata,
                              content_hash=content_hash(metadata["filename"], url)))
            public_changed = True
        elif attachment.filename != metadata["filename"] or attachment.type != metadata["type"]:
            attachment.filename, attachment.type = metadata["filename"], metadata["type"]
            attachment.content_hash = content_hash(attachment.filename, url)
            attachment.extracted_text = None
            public_changed = True
    for url in old_owned - desired.keys():
        if url in existing:
            db.delete(existing[url])
            public_changed = True
    _save(db, notice, value)
    # A legacy relation may only have an attempt marker. Its first successful
    # adoption is not evidence that attachments changed from an empty set.
    changed = public_changed or (previous is not None and previous.get("checked_at") is not None and old_files != files)
    return changed, _fingerprint(old_files), _fingerprint(files)
