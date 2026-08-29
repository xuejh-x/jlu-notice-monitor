from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import get_settings, load_yaml
from app.parsers import parse_detail_html, parse_list_html
from app.schemas.notice import NoticeCandidate


class SourceError(RuntimeError):
    pass


class LoginExpiredError(SourceError):
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
            timeout=settings.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": str(crawler_config.get("user_agent", "JLUNoticeMonitor/0.1"))},
        )

    async def _get(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                if not response.encoding or response.encoding.lower() == "iso-8859-1":
                    response.encoding = response.charset_encoding or "utf-8"
                return response.text
            except (httpx.HTTPError, UnicodeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff * (attempt + 1))
        raise SourceError(f"GET {url} failed: {last_error}")

    async def fetch_list(self) -> list[NoticeCandidate]:
        notices: list[NoticeCandidate] = []
        seen: set[str] = set()
        for section in self.config.get("sections", []):
            url = str(section["url"])
            html = await self._get(url)
            parsed = self.parse_list(html, url, str(section.get("name", "")))
            for item in parsed[: self.max_items]:
                if item.url not in seen:
                    seen.add(item.url)
                    notices.append(item)
        return notices

    def parse_list(self, html: str, page_url: str, section: str) -> list[NoticeCandidate]:
        return parse_list_html(html, page_url, section)

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        html = await self._get(notice.url)
        return self.parse_detail(html, notice)

    def parse_detail(self, html: str, notice: NoticeCandidate) -> NoticeCandidate:
        return parse_detail_html(html, notice.url, notice)

    async def close(self) -> None:
        await self.client.aclose()
