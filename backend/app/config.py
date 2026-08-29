from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_prefix="JLU_",
        extra="ignore",
    )

    database_url: str = "sqlite:///data/notices.db"
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
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        path = Path(self.database_url.removeprefix(prefix))
        return path if path.is_absolute() else BACKEND_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_yaml(name: str) -> dict[str, Any]:
    path = BACKEND_DIR / "config" / name
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}
