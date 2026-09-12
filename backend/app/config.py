from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import BACKEND_DIR, get_database_path



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_prefix="JLU_",
        extra="ignore",
    )

    environment: str = "development"
    app_data_dir: str | None = None
    database_url: str | None = None
    host: str = "127.0.0.1"
    port: int = Field(8000, ge=1, le=65535)
    log_level: str = "INFO"
    request_timeout: float = 20.0
    max_items_per_section: int = 30
    bootstrap_recent_days: int = 7
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://tauri.localhost",
        ]
    )
    oa_headless: bool = True
    scheduler_enabled: bool | None = None
    scheduler_interval_minutes: int | None = Field(default=None, ge=1)
    deployment_role: str | None = None
    public_feed_url: str | None = None
    cloud_feed_stale_after_seconds: int = Field(default=3600, ge=60, le=86400)
    source_max_response_bytes: int = Field(default=5_000_000, ge=100_000, le=20_000_000)
    source_max_pages: int = Field(default=3, ge=1, le=5)
    source_run_timeout_seconds: int = Field(default=120, ge=30, le=600)
    startup_sync_enabled: bool | None = None
    admin_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NOTICE_HUB_ADMIN_KEY", "JLU_ADMIN_KEY"),
    )
    cloud_admin_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NOTICE_HUB_CLOUD_ADMIN_URL", "JLU_CLOUD_ADMIN_URL"),
    )
    admin_auth_attempts_per_minute: int = Field(default=10, ge=1, le=120)
    min_cloud_crawl_interval_seconds: int = Field(default=900, ge=300, le=86400)

    @property
    def effective_deployment_role(self) -> str:
        if self.deployment_role:
            return self.deployment_role.strip().lower()
        return "desktop" if self.environment == "production" else "standalone"

    @property
    def effective_startup_sync_enabled(self) -> bool:
        if self.startup_sync_enabled is not None:
            return self.startup_sync_enabled
        # Both the packaged Desktop backend and the ordinary local/standalone
        # backend own a local database and should refresh it after readiness.
        # Cloud keeps its scheduler-only lifecycle so a deploy/restart does not
        # create an extra production crawl.
        return self.effective_deployment_role != "cloud"

    @property
    def database_path(self) -> Path | None:
        if not self.database_url:
            return get_database_path(self.environment, self.app_data_dir)
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        path = Path(self.database_url.removeprefix(prefix))
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def effective_database_url(self) -> str:
        if self.database_path is not None:
            return f"sqlite:///{self.database_path.as_posix()}"
        assert self.database_url is not None
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_yaml(name: str) -> dict[str, Any]:
    path = BACKEND_DIR / "config" / name
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}
