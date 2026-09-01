from __future__ import annotations

from datetime import UTC, datetime

_started_at: datetime | None = None
_initialized = False


def mark_started() -> None:
    global _started_at, _initialized
    _started_at = datetime.now(UTC).replace(tzinfo=None)
    _initialized = True


def mark_stopped() -> None:
    global _initialized
    _initialized = False


def status() -> dict[str, object]:
    now = datetime.now(UTC).replace(tzinfo=None)
    return {
        "initialized": _initialized,
        "started_at": _started_at,
        "uptime_seconds": round((now - _started_at).total_seconds(), 3) if _started_at else 0,
    }
