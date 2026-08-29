from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
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
        ]
    )
    oa_headless: bool = True

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
