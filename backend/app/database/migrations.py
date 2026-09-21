from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import Engine, inspect, text

from app.services.source_identity import source_identity
from app.services.notice_identity import origin_item_key


SOURCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("ownership", "VARCHAR(40) NOT NULL DEFAULT 'OFFICIAL_CLOUD'"),
    ("source_type", "VARCHAR(40) NOT NULL DEFAULT 'generic_html'"),
    ("parser", "VARCHAR(80) NOT NULL DEFAULT 'generic_html'"),
    ("parser_config", "TEXT NOT NULL DEFAULT '{}'"),
    ("subscribed", "BOOLEAN NOT NULL DEFAULT 1"),
    ("auth_type", "VARCHAR(40) NOT NULL DEFAULT 'none'"),
    ("auth_username", "VARCHAR(300)"),
    ("credential_ref", "VARCHAR(300)"),
    ("login_url", "VARCHAR(2000)"),
    ("session_profile_ref", "VARCHAR(300)"),
    ("allow_private_network", "BOOLEAN NOT NULL DEFAULT 0"),
    ("health_state", "VARCHAR(40) NOT NULL DEFAULT 'unconfigured'"),
    ("last_error_code", "VARCHAR(80)"),
    ("reauth_notified_at", "DATETIME"),
    ("created_at", "DATETIME"),
    ("updated_at", "DATETIME"),
    ("is_deleted", "BOOLEAN NOT NULL DEFAULT 0"),
)

GATE13_SOURCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_identity", "VARCHAR(64)"),
    ("cloud_source_id", "VARCHAR(80)"),
    ("source_scope", "VARCHAR(20) NOT NULL DEFAULT 'personal'"),
    ("execution", "VARCHAR(20) NOT NULL DEFAULT 'local'"),
    ("cloud_policy", "VARCHAR(20) NOT NULL DEFAULT 'auto'"),
    ("crawl_interval_seconds", "INTEGER"),
    ("validation_status", "VARCHAR(20) NOT NULL DEFAULT 'untested'"),
    ("validated_at", "DATETIME"),
)

STAGE17_1_SOURCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("execution_policy", "VARCHAR(24) NOT NULL DEFAULT 'cloud_preferred'"),
)

NOTICE_COLUMNS: tuple[tuple[str, str], ...] = (("public_id", "VARCHAR(80)"),)

STAGE17_2_RELATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("origin_item_key", "VARCHAR(160)"),
)

PHASE15_NOTICE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("version", "INTEGER NOT NULL DEFAULT 1"),
)

PHASE15_ATTACHMENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("content_hash", "VARCHAR(64)"),
    ("created_at", "DATETIME"),
)


def _add_missing_columns(engine: Engine, table: str, columns: Iterable[tuple[str, str]]) -> None:
    existing = {column["name"] for column in inspect(engine).get_columns(table)}
    with engine.begin() as connection:
        for name, declaration in columns:
            if name not in existing:
                connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}'))


def run_gate12_migrations(engine: Engine) -> None:
    """Perform the additive Gate 12 migration without replacing existing data."""

    if engine.dialect.name != "sqlite":
        return
    _add_missing_columns(engine, "sources", SOURCE_COLUMNS)
    _add_missing_columns(engine, "notices", NOTICE_COLUMNS)
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_notices_public_id ON notices (public_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sources_ownership ON sources (ownership)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sources_subscribed ON sources (subscribed)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sources_health_state ON sources (health_state)"))
        connection.execute(
            text(
                "UPDATE sources SET ownership = CASE WHEN code = 'oa' "
                "THEN 'CUSTOM_LOCAL_PRIVATE' ELSE 'OFFICIAL_CLOUD' END "
                "WHERE ownership IS NULL OR ownership = ''"
            )
        )
        connection.execute(
            text(
                "UPDATE sources SET ownership = CASE WHEN code = 'oa' THEN 'CUSTOM_LOCAL_PRIVATE' ELSE 'OFFICIAL_CLOUD' END, "
                "source_type = CASE WHEN code = 'oa' "
                "THEN 'private_browser' ELSE 'official_adapter' END, "
                "parser = code, auth_type = CASE WHEN code = 'oa' THEN 'browser_session' ELSE 'none' END, "
                "health_state = CASE WHEN enabled = 0 THEN 'disabled' "
                "WHEN last_error = 'OA_LOGIN_EXPIRED' THEN 'needs_reauth' "
                "WHEN last_error IS NOT NULL THEN 'source_error' "
                "WHEN last_success_at IS NOT NULL THEN 'healthy' ELSE 'unconfigured' END, "
                "created_at = COALESCE(created_at, :now), updated_at = COALESCE(updated_at, :now) "
                "WHERE code IN ('cse', 'ccst', 'csw', 'jwc', 'innovation', 'oa')"
            ),
            {"now": now},
        )
        connection.execute(
            text("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES ('12.0', :now)"),
            {"now": now},
        )


def run_gate13_migrations(engine: Engine) -> None:
    """Add Gate 13 source identity and cloud policy metadata without replacing rows."""

    if engine.dialect.name != "sqlite":
        return
    _add_missing_columns(engine, "sources", GATE13_SOURCE_COLUMNS)
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sources_source_identity ON sources (source_identity)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sources_cloud_source_id ON sources (cloud_source_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sources_cloud_policy ON sources (cloud_policy)"))
        connection.execute(
            text(
                "UPDATE sources SET source_scope = CASE "
                "WHEN ownership = 'OFFICIAL_CLOUD' THEN 'official' "
                "WHEN ownership = 'SHARED_CLOUD' THEN 'shared' "
                "WHEN ownership = 'CUSTOM_LOCAL_PRIVATE' THEN 'private' ELSE 'personal' END, "
                "execution = CASE WHEN ownership IN ('OFFICIAL_CLOUD', 'SHARED_CLOUD') THEN 'cloud' ELSE 'local' END, "
                "cloud_policy = COALESCE(NULLIF(cloud_policy, ''), 'auto'), "
                "validation_status = CASE WHEN ownership IN ('OFFICIAL_CLOUD', 'SHARED_CLOUD', 'CUSTOM_LOCAL_PUBLIC') "
                "THEN 'passed' ELSE COALESCE(NULLIF(validation_status, ''), 'untested') END"
            )
        )
        rows = connection.execute(
            text("SELECT id, base_url FROM sources WHERE source_identity IS NULL OR source_identity = ''")
        ).mappings()
        for row in rows:
            try:
                identity = source_identity(str(row["base_url"] or ""))
            except ValueError:
                continue
            connection.execute(
                text("UPDATE sources SET source_identity = :identity WHERE id = :source_id"),
                {"identity": identity, "source_id": row["id"]},
            )
        connection.execute(
            text("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES ('13.0', :now)"),
            {"now": now},
        )


def run_gate14_migrations(engine: Engine) -> None:
    """Seed the additive Gate 14 local notification schema idempotently."""

    if engine.dialect.name != "sqlite":
        return
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT OR IGNORE INTO notification_preferences "
                "(id, enabled, new_notice_enabled, important_notice_enabled, deadline_enabled, "
                "source_health_enabled, daily_summary_enabled, minimum_importance, deadline_lead_days, "
                "quiet_start, quiet_end, daily_summary_time, created_at, updated_at) VALUES "
                "(1, 0, 1, 1, 1, 1, 1, 70, '7,3,1', '23:00', '08:00', '09:00', :now, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES ('14.0', :now)"),
            {"now": now},
        )


def run_stage17_1_migrations(engine: Engine) -> None:
    """Add execution policy metadata without changing legacy execution behavior."""

    if engine.dialect.name != "sqlite":
        return
    _add_missing_columns(engine, "sources", STAGE17_1_SOURCE_COLUMNS)
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        migration_applied = connection.scalar(
            text("SELECT 1 FROM schema_migrations WHERE version = '17.1'")
        ) is not None
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sources_execution_policy ON sources (execution_policy)"))
        if not migration_applied:
            connection.execute(
                text(
                    "UPDATE sources SET execution_policy = CASE "
                    "WHEN ownership = 'OFFICIAL_CLOUD' THEN 'cloud_preferred' "
                    "WHEN ownership = 'SHARED_CLOUD' THEN 'cloud_only' "
                    "ELSE 'local_only' END"
                )
            )
        connection.execute(
            text("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES ('17.1', :now)"),
            {"now": now},
        )


def run_stage17_2_migrations(engine: Engine) -> None:
    """Add source-scoped notice identity without rebuilding existing relations."""

    if engine.dialect.name != "sqlite":
        return
    _add_missing_columns(engine, "notice_source_relations", STAGE17_2_RELATION_COLUMNS)
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT id, source_url FROM notice_source_relations "
                "WHERE origin_item_key IS NULL OR origin_item_key = ''"
            )
        ).mappings()
        for row in rows:
            connection.execute(
                text(
                    "UPDATE notice_source_relations SET origin_item_key = :origin_item_key "
                    "WHERE id = :relation_id"
                ),
                {
                    "origin_item_key": origin_item_key(None, str(row["source_url"])),
                    "relation_id": row["id"],
                },
            )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_notice_source_origin_item_key "
                "ON notice_source_relations (source_id, origin_item_key)"
            )
        )
        connection.execute(
            text("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES ('17.2', :now)"),
            {"now": now},
        )


def run_phase15_cloud_data_migrations(engine: Engine) -> None:
    """Add sync-ready public fact metadata to existing Desktop SQLite databases."""

    if engine.dialect.name != "sqlite":
        return
    _add_missing_columns(engine, "notices", PHASE15_NOTICE_COLUMNS)
    _add_missing_columns(engine, "attachments", PHASE15_ATTACHMENT_COLUMNS)
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
    with engine.begin() as connection:
        connection.execute(text("UPDATE notices SET version = 1 WHERE version IS NULL OR version < 1"))
        connection.execute(text("UPDATE attachments SET created_at = :now WHERE created_at IS NULL"), {"now": now})
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notices_version ON notices (version)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_attachments_content_hash ON attachments (content_hash)"))
        connection.execute(
            text("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES ('phase-1.5', :now)"),
            {"now": now},
        )
