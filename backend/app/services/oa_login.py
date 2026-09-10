from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
import logging
from typing import Any

from app.database import SessionLocal
from app.logging_config import log_event
from app.models import Source
from app.sources.base import LoginExpiredError, SourceError
from app.sources.oa import OASource


logger = logging.getLogger(__name__)


class OALoginCoordinator:
    """Own one interactive OA login window without accepting user credentials."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self.source_id: int | None = None
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.outcome: str | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, source_id: int, config: dict[str, Any]) -> bool:
        if self.running:
            return False
        OASource.ensure_runtime_available()
        self.source_id = source_id
        self.started_at = datetime.now(UTC).replace(tzinfo=None)
        self.completed_at = None
        self.outcome = "login_window_opened"
        self._task = asyncio.create_task(self._run(source_id, config), name="oa-interactive-login")
        self._task.add_done_callback(self._log_task_result)
        return True

    async def _run(self, source_id: int, config: dict[str, Any]) -> None:
        adapter = OASource(config)
        try:
            result = await adapter.login_setup()
        except asyncio.CancelledError:
            self.outcome = "cancelled"
            raise
        except LoginExpiredError as exc:
            self.outcome = "authentication_required"
            self._update_source(source_id, "needs_reauth", str(exc) or "OA_LOGIN_REQUIRED")
        except SourceError as exc:
            self.outcome = "error"
            error_code = str(exc) or "OA_LOGIN_ERROR"
            state = "network_error" if error_code.startswith("OA_HTTP_") else "auth_error"
            self._update_source(source_id, state, error_code)
        except Exception as exc:
            self.outcome = "error"
            self._update_source(source_id, "auth_error", f"OA_LOGIN_{type(exc).__name__.upper()}")
        else:
            self.outcome = result
            if result == "ready":
                self._update_source(source_id, "authenticated", None, enabled=True, validated=True)
            else:
                self._update_source(
                    source_id,
                    "unconfigured",
                    "OA_PARSER_UNCONFIGURED",
                    enabled=False,
                    validated=False,
                )
        finally:
            await adapter.close()
            self.completed_at = datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _update_source(
        source_id: int,
        state: str,
        error_code: str | None,
        *,
        enabled: bool | None = None,
        validated: bool | None = None,
    ) -> None:
        with SessionLocal() as db:
            source = db.get(Source, source_id)
            if source is None:
                return
            source.health_state = state
            source.last_error_code = error_code
            source.last_error = error_code
            if enabled is not None:
                source.enabled = enabled
            if validated is not None:
                source.validation_status = "passed" if validated else "untested"
                source.validated_at = datetime.now(UTC).replace(tzinfo=None) if validated else None
            db.commit()

    @staticmethod
    def _log_task_result(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "oa_login_task_failed",
                error_type=type(exc).__name__,
            )

    async def shutdown(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "source_id": self.source_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outcome": self.outcome,
        }


oa_login_coordinator = OALoginCoordinator()
