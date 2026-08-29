from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import BACKEND_DIR, get_settings


def configure_logging() -> None:
    log_dir = BACKEND_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, get_settings().log_level.upper(), logging.INFO))
    root.addHandler(file_handler)
    root.addHandler(console_handler)

