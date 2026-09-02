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
    ownership: Mapped[str] = mapped_column(String(40), default="OFFICIAL_CLOUD", index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="generic_html")
    parser: Mapped[str] = mapped_column(String(80), default="generic_html")
    parser_config: Mapped[str] = mapped_column(Text, default="{}")
    subscribed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    auth_type: Mapped[str] = mapped_column(String(40), default="none")
    auth_username: Mapped[str | None] = mapped_column(String(300))
    credential_ref: Mapped[str | None] = mapped_column(String(300))
    login_url: Mapped[str | None] = mapped_column(String(2000))
    session_profile_ref: Mapped[str | None] = mapped_column(String(300))
    allow_private_network: Mapped[bool] = mapped_column(Boolean, default=False)
    health_state: Mapped[str] = mapped_column(String(40), default="unconfigured", index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    reauth_notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_identity: Mapped[str | None] = mapped_column(String(64), index=True)
    cloud_source_id: Mapped[str | None] = mapped_column(String(80), index=True)
    source_scope: Mapped[str] = mapped_column(String(20), default="personal", index=True)
    execution: Mapped[str] = mapped_column(String(20), default="local", index=True)
    cloud_policy: Mapped[str] = mapped_column(String(20), default="auto", index=True)
    crawl_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(String(20), default="untested")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime)

    relations: Mapped[list[NoticeSourceRelation]] = relationship(back_populates="source")


class Notice(Base):
    __tablename__ = "notices"
    __table_args__ = (
        Index("ix_notices_category_score", "category", "importance_score"),
        Index("ix_notices_dates", "publish_date", "registration_deadline"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
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
    __table_args__ = (
        Index("ix_user_states_favorite", "is_favorite"),
        Index("ix_user_states_read", "is_read"),
    )

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


class ImportanceRule(Base):
    __tablename__ = "importance_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    weight: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_system_default: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
