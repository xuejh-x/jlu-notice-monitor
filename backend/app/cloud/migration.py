from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Attachment, Notice, NoticeSourceRelation, NoticeUpdate, Source


SEQUENCED_TABLES = (
    "sources",
    "notices",
    "notice_source_relations",
    "notice_updates",
    "attachments",
)


@dataclass(frozen=True)
class MigrationSummary:
    sources: int
    notices: int
    attachments: int
    relations: int
    updates: int


def _copy(row, model):
    return model(**{column.name: getattr(row, column.name) for column in model.__table__.columns})


def _copy_public_source(row: Source) -> Source:
    copied = _copy(row, Source)
    copied.auth_username = None
    copied.credential_ref = None
    copied.session_profile_ref = None
    copied.allow_private_network = False
    return copied


def _sync_postgresql_sequences(db: Session) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    for table in SEQUENCED_TABLES:
        db.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table}"
            )
        )


def migrate_public_data(source_db: Session, target_db: Session) -> MigrationSummary:
    """Idempotently copy public facts while preserving integer IDs.

    Personal state, favorites, notification preferences and deliveries are
    intentionally excluded from the Cloud data layer.
    """

    sources = source_db.scalars(
        select(Source).where(
            Source.ownership.in_(("OFFICIAL_CLOUD", "SHARED_CLOUD")),
            Source.is_deleted.is_(False),
        )
    ).all()
    source_ids = {item.id for item in sources}
    for item in sources:
        target_db.merge(_copy_public_source(item))
    target_db.flush()

    notices = source_db.scalars(select(Notice).where(Notice.source_id.in_(source_ids))).all()
    notice_ids = {item.id for item in notices}
    for item in notices:
        target_db.merge(_copy(item, Notice))
    target_db.flush()

    relations = source_db.scalars(
        select(NoticeSourceRelation).where(
            NoticeSourceRelation.notice_id.in_(notice_ids),
            NoticeSourceRelation.source_id.in_(source_ids),
        )
    ).all()
    attachments = source_db.scalars(select(Attachment).where(Attachment.notice_id.in_(notice_ids))).all()
    updates = source_db.scalars(select(NoticeUpdate).where(NoticeUpdate.notice_id.in_(notice_ids))).all()
    for model, rows in (
        (NoticeSourceRelation, relations),
        (Attachment, attachments),
        (NoticeUpdate, updates),
    ):
        for item in rows:
            target_db.merge(_copy(item, model))
    target_db.flush()
    _sync_postgresql_sequences(target_db)
    target_db.commit()
    return MigrationSummary(
        sources=len(sources), notices=len(notices), attachments=len(attachments),
        relations=len(relations), updates=len(updates),
    )
