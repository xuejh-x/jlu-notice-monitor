from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

from app.logging_config import log_event
from app.services.chrome_session import inspect_chrome_environment
from app.services.credentials import CredentialStorageUnavailable
from app.sources.base import SourceError
from app.sources.oa import OASource


logger = logging.getLogger(__name__)


class OALoginCoordinator:
    """Own the local Chrome CDP session between Start login and Detect status."""

    def __init__(self) -> None:
        self._adapter: OASource | None = None
        self.source_id: int | None = None
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.outcome: str | None = None

    @property
    def running(self) -> bool:
        return self._adapter is not None

    def environment(self) -> dict[str, Any]:
        result = inspect_chrome_environment().to_dict()
        result["session_active"] = self.running
        result["source_id"] = self.source_id
        return result

    async def start(self, source_id: int, config: dict[str, Any]) -> bool:
        if self.running:
            if self.source_id == source_id:
                return False
            await self.shutdown()
        OASource.ensure_runtime_available()
        adapter = OASource(config)
        try:
            await adapter.open_login_window()
        except Exception:
            await adapter.close()
            raise
        self._adapter = adapter
        self.source_id = source_id
        self.started_at = datetime.now(UTC).replace(tzinfo=None)
        self.completed_at = None
        self.outcome = "chrome_login_opened"
        return True

    async def detect(self, source_id: int, config: dict[str, Any]) -> dict[str, Any]:
        if not self.running or self.source_id != source_id:
            return {
                "status": "not_authenticated",
                "reason": "OA_CHROME_SESSION_NOT_STARTED",
                "message": "尚未启动 OA Chrome 登录，请先点击首次登录。",
            }
        assert self._adapter is not None
        reference = str(config.get("credential_ref") or f"oa-session-{config['code']}")
        try:
            authenticated = await self._adapter.capture_session(reference)
        except CredentialStorageUnavailable as exc:
            self.outcome = "storage_unavailable"
            raise SourceError("OA_SECURE_STORAGE_UNAVAILABLE") from exc
        if not authenticated:
            self.outcome = "authentication_pending"
            return {
                "status": "not_authenticated",
                "reason": "OA_LOGIN_NOT_COMPLETED",
                "message": "尚未检测到 OA 登录状态，请在 Chrome 中完成登录后重试。",
            }
        self.outcome = "authenticated"
        self.completed_at = datetime.now(UTC).replace(tzinfo=None)
        await self.shutdown(preserve_outcome=True)
        return {
            "status": "authenticated",
            "reason": None,
            "message": "OA 登录成功，认证信息已使用 Windows 本机加密保存，可以开始抓取。",
            "credential_reference": reference,
        }

    async def shutdown(self, *, preserve_outcome: bool = False) -> None:
        if self._adapter is not None:
            try:
                await self._adapter.close()
            except Exception as exc:
                log_event(logger, logging.WARNING, "oa_chrome_close_failed", error_type=type(exc).__name__)
        self._adapter = None
        self.source_id = None
        if not preserve_outcome and self.outcome not in {"authenticated", "storage_unavailable"}:
            self.outcome = "cancelled"

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "source_id": self.source_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outcome": self.outcome,
        }


oa_login_coordinator = OALoginCoordinator()
