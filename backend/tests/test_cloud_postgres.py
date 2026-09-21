from __future__ import annotations

import os
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.cloud.migration import migrate_public_data
from app.config import get_settings
from app.database import Base
from app.models import Notice, Source
from app.paths import BACKEND_DIR


POSTGRES_URL = os.getenv("JLU_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set JLU_TEST_POSTGRES_URL to the disposable PostgreSQL test database",
)


def test_postgresql_migration_crud_and_sqlite_copy(monkeypatch) -> None:
    assert POSTGRES_URL is not None
    database_name = make_url(POSTGRES_URL).database or ""
    assert database_name.endswith("_test"), "refusing to modify a database not ending in _test"
    monkeypatch.setenv("JLU_DATABASE_URL", POSTGRES_URL)
    get_settings.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    sqlite_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(sqlite_engine)
    postgres_engine = create_engine(POSTGRES_URL)
    try:
        with Session(sqlite_engine) as source_db, Session(postgres_engine) as target_db:
            source = Source(id=100, code="integration", name="Integration", base_url="https://example.test")
            source_db.add(source)
            source_db.flush()
            source_db.add(
                Notice(
                    id=200,
                    title="PostgreSQL",
                    normalized_title="postgresql",
                    url="https://example.test/postgresql",
                    canonical_url="https://example.test/postgresql",
                    publish_date=date(2026, 9, 13),
                    source_id=source.id,
                    content="body",
                    content_hash="p" * 64,
                )
            )
            source_db.commit()
            summary = migrate_public_data(source_db, target_db)
            assert summary.sources == 1 and summary.notices == 1
            assert target_db.scalar(select(func.count(Notice.id))) == 1
            inserted = Source(code="after-copy", name="After", base_url="https://after.test")
            target_db.add(inserted)
            target_db.commit()
            assert inserted.id > 100
            inserted.name = "Updated"
            target_db.commit()
            assert target_db.get(Source, inserted.id).name == "Updated"
            inserted_id = inserted.id
            target_db.delete(inserted)
            target_db.commit()
            assert target_db.get(Source, inserted_id) is None
    finally:
        sqlite_engine.dispose()
        postgres_engine.dispose()
        command.downgrade(config, "base")
        get_settings.cache_clear()
