from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import Engine, inspect, text

from app.services.source_identity import source_identity


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

NOTICE_COLUMNS: tuple[tuple[str, str], ...] = (("public_id", "VARCHAR(80)"),)


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
