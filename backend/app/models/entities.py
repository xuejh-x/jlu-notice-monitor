from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)

    relations: Mapped[list[NoticeSourceRelation]] = relationship(back_populates="source")


class Notice(Base):
    __tablename__ = "notices"
    __table_args__ = (
        Index("ix_notices_category_score", "category", "importance_score"),
        Index("ix_notices_dates", "publish_date", "registration_deadline"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(1000))
    normalized_title: Mapped[str] = mapped_column(String(1000), index=True)
    url: Mapped[str] = mapped_column(String(2000))
    canonical_url: Mapped[str] = mapped_column(String(2000), index=True)
    publish_date: Mapped[date | None] = mapped_column(Date, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    publisher: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(80), default="other", index=True)
    importance_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    registration_start: Mapped[date | None] = mapped_column(Date)
    registration_deadline: Mapped[date | None] = mapped_column(Date, index=True)
    event_start: Mapped[date | None] = mapped_column(Date)
    event_end: Mapped[date | None] = mapped_column(Date)
    target_students: Mapped[str | None] = mapped_column(Text)
    registration_method: Mapped[str | None] = mapped_column(Text)
    competition_level: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    source: Mapped[Source] = relationship()
    source_relations: Mapped[list[NoticeSourceRelation]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )
    updates: Mapped[list[NoticeUpdate]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )
    user_state: Mapped[UserState | None] = relationship(
        back_populates="notice", cascade="all, delete-orphan", uselist=False
    )


class NoticeSourceRelation(Base):
    __tablename__ = "notice_source_relations"
    __table_args__ = (UniqueConstraint("notice_id", "source_id", "source_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    content_hash: Mapped[str] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    notice: Mapped[Notice] = relationship(back_populates="source_relations")
    source: Mapped[Source] = relationship(back_populates="relations")


class NoticeUpdate(Base):
    __tablename__ = "notice_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    old_hash: Mapped[str] = mapped_column(String(64))
    new_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)

    notice: Mapped[Notice] = relationship(back_populates="updates")


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (UniqueConstraint("notice_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str] = mapped_column(String(2000))
    type: Mapped[str] = mapped_column(String(20))
    extracted_text: Mapped[str | None] = mapped_column(Text)

    notice: Mapped[Notice] = relationship(back_populates="attachments")


class UserState(Base):
    __tablename__ = "user_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"), unique=True, index=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    notice: Mapped[Notice] = relationship(back_populates="user_state")


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"), unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
