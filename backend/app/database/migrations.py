from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import Engine, inspect, text


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
            text(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) "
                "VALUES ('12.0', :now)"
            ),
            {"now": now},
        )
