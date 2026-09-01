from __future__ import annotations

import json
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.config import get_settings
from app.paths import get_log_dir

_SENSITIVE_KEY = re.compile(r"(password|token|cookie|authorization|credential|secret)", re.I)
_AUTH_VALUE = re.compile(r"(?i)(authorization\s*[:=]\s*)[^\r\n]+")


def _safe_value(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        if value.lower().startswith(("http://", "https://")):
            parts = urlsplit(value)
            return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return _AUTH_VALUE.sub(r"\1[REDACTED]", value)
    if isinstance(value, dict):
        return {str(name): _safe_value(item, str(name)) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return value


class PrivacyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _safe_value(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        for key in ("source", "trigger_source", "duration_seconds", "status", "new_count", "updated_count", "unchanged_count", "error_type", "error"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = _safe_value(value, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info).splitlines()[-1]
        return json.dumps(payload, ensure_ascii=False, default=str)


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    logger.log(level, event, extra={"event": event, **_safe_value(context)})


def configure_logging(
    *, log_dir: Path | None = None, max_bytes: int = 5_000_000, backup_count: int = 5
) -> Path:
    settings = get_settings()
    target_dir = log_dir or get_log_dir(settings.environment, settings.app_data_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    formatter = JsonFormatter()
    file_handler = RotatingFileHandler(
        target_dir / "app.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    console_handler = logging.StreamHandler()
    for handler in (file_handler, console_handler):
        handler.setFormatter(formatter)
        handler.addFilter(PrivacyFilter())
    root = logging.getLogger()
    for handler in root.handlers:
        handler.close()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    return target_dir / "app.log"
