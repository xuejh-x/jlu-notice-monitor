from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIRECTORY_NAME = "JLU Notice Monitor"


def get_environment(environment: str | None = None) -> str:
    value = environment if environment is not None else os.getenv("JLU_ENVIRONMENT", "development")
    return value.strip().lower() or "development"


def _override_dir(override: str | Path | None = None) -> Path | None:
    configured = str(override or os.getenv("JLU_APP_DATA_DIR", "")).strip()
    if not configured:
        return None
    path = Path(configured).expanduser()
    return path if path.is_absolute() else BACKEND_DIR / path


def get_app_data_dir(environment: str | None = None, override: str | Path | None = None) -> Path:
    override_path = _override_dir(override)
    if override_path is not None:
        return override_path
    if get_environment(environment) == "production":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / APP_DIRECTORY_NAME
    return BACKEND_DIR


def get_database_path(environment: str | None = None, override: str | Path | None = None) -> Path:
    return get_app_data_dir(environment, override) / "data" / "notices.db"


def get_log_dir(environment: str | None = None, override: str | Path | None = None) -> Path:
    return get_app_data_dir(environment, override) / "logs"


def get_oa_profile_dir(environment: str | None = None, override: str | Path | None = None) -> Path:
    if get_environment(environment) == "production" or _override_dir(override) is not None:
        return get_app_data_dir(environment, override) / "oa-profile"
    return get_app_data_dir(environment, override) / "data" / "browser_profile" / "oa"


def get_cache_dir(environment: str | None = None, override: str | Path | None = None) -> Path:
    return get_app_data_dir(environment, override) / "cache"


def get_runtime_config_dir(environment: str | None = None, override: str | Path | None = None) -> Path:
    if get_environment(environment) == "production" or _override_dir(override) is not None:
        return get_app_data_dir(environment, override) / "config"
    return get_app_data_dir(environment, override) / "data" / "runtime-config"


def ensure_runtime_directories(environment: str | None = None, override: str | Path | None = None) -> None:
    for path in (
        get_database_path(environment, override).parent,
        get_log_dir(environment, override),
        get_oa_profile_dir(environment, override),
        get_cache_dir(environment, override),
        get_runtime_config_dir(environment, override),
    ):
        path.mkdir(parents=True, exist_ok=True)
