from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import get_settings, load_yaml
from app.logging_config import log_event
from app.parsers import parse_detail_html, parse_list_html
from app.parsers.html import is_empty_notice_list
from app.schemas.notice import NoticeCandidate
from app.services.http_diagnostics import exception_summary, is_retryable_http_error
from app.services.source_security import UnsafeSourceUrl, validate_local_source_url
from app.services.tls import is_certificate_verification_error, source_ssl_context

logger = logging.getLogger(__name__)


class SourceError(RuntimeError):
    pass


class LoginExpiredError(SourceError):
    pass


class SourceNotConfiguredError(SourceError):
    pass


class NoticeSource(ABC):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.code = str(config["code"])
        self.name = str(config["name"])
        self.base_url = str(config["base_url"])

    @abstractmethod
    async def fetch_list(self) -> list[NoticeCandidate]: ...

    @abstractmethod
    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate: ...

    async def health_check(self) -> bool:
        return bool(await self.fetch_list())

    async def close(self) -> None:
        return None


class StaticHTMLSource(NoticeSource):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        settings = get_settings()
        crawler_config = load_yaml("settings.yaml").get("crawler", {})
        self.max_items = settings.max_items_per_section
        self.retries = int(crawler_config.get("retries", 2))
        self.backoff = float(crawler_config.get("retry_backoff_seconds", 1.0))
        self.client = httpx.AsyncClient(
            verify=source_ssl_context(),
            timeout=settings.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": str(crawler_config.get("user_agent", "JLUNoticeMonitor/0.1"))},
        )

    async def _get(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            started = time.perf_counter()
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                if not response.encoding or response.encoding.lower() == "iso-8859-1":
                    response.encoding = response.charset_encoding or "utf-8"
                text = response.text
                self._log_http_result("GET", url, attempt, started, response=response)
                return text
            except (httpx.HTTPError, UnicodeError) as exc:
                self._log_http_result("GET", url, attempt, started, error=exc)
                if is_certificate_verification_error(exc):
                    raise SourceError(f"TLS_CERTIFICATE_VERIFY_FAILED: GET {url}: {exception_summary(exc)}") from exc
                last_error = exc
                if attempt < self.retries and is_retryable_http_error(exc):
                    await asyncio.sleep(self.backoff * (attempt + 1))
                else:
                    break
        raise SourceError(f"GET {url} failed: {exception_summary(last_error)}") from last_error

    def _log_http_result(
        self, method: str, url: str, attempt: int, started: float, *,
        response: httpx.Response | None = None, error: Exception | None = None,
    ) -> None:
        if isinstance(error, httpx.HTTPStatusError):
            response = error.response
        log_event(
            logger, logging.WARNING if error else logging.INFO,
            "source_http_request_failed" if error else "source_http_request_succeeded",
            source=self.code, method=method, url=url,
            attempt=attempt + 1, max_attempts=self.retries + 1,
            duration_seconds=round(time.perf_counter() - started, 3),
            timeout_seconds=self.client.timeout.as_dict(),
            http_status=response.status_code if response is not None else None,
            response_bytes=len(response.content) if response is not None else None,
            content_type=response.headers.get("content-type") if response is not None else None,
            error_type=type(error).__name__ if error else None,
            error=exception_summary(error) if error else None,
        )

    async def fetch_list(self) -> list[NoticeCandidate]:
        notices: list[NoticeCandidate] = []
        seen: set[str] = set()
        for section in self.config.get("sections", []):
            url = str(section["url"])
            html = await self._get(url)
            parsed = self.parse_list(html, url, str(section.get("name", "")))
            if not parsed and not is_empty_notice_list(html):
                raise SourceError("HTML_LIST_UNSUPPORTED: no verified article links; configure a list selector")
            for item in parsed[: self.max_items]:
                if item.url not in seen:
                    seen.add(item.url)
                    notices.append(item)
        return notices

    def parse_list(self, html: str, page_url: str, section: str) -> list[NoticeCandidate]:
        return parse_list_html(html, page_url, section)

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        html = await self._get(notice.url)
        parsed = self.parse_detail(html, notice)
        attachments = []
        for attachment in parsed.attachments:
            try:
                await validate_local_source_url(attachment.url, allow_private_network=False)
            except UnsafeSourceUrl:
                continue
            attachments.append(attachment)
        if not parsed.content and not attachments:
            raise SourceError("HTML_DETAIL_EMPTY: no content or permitted attachment remains")
        return parsed.model_copy(update={"attachments": attachments})

    def parse_detail(self, html: str, notice: NoticeCandidate) -> NoticeCandidate:
        return parse_detail_html(html, notice.url, notice)

    async def close(self) -> None:
        await self.client.aclose()


class SinglePageSource(StaticHTMLSource):
    """Opt-in snapshot adapter. Only the runner may persist its baseline."""

    snapshot: dict[str, Any] | None = None

    @abstractmethod
    def parse_snapshot(self, html: str) -> dict[str, Any]: ...

    async def fetch_list(self) -> list[NoticeCandidate]:
        self.snapshot = self.parse_snapshot(await self._get(self.base_url))
        return []

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        return notice

    async def health_check(self) -> bool:
        await self.fetch_list()
        return self.snapshot is not None
