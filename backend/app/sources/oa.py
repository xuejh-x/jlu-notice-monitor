from __future__ import annotations

import asyncio
import json
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import parse_qsl, urlencode, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from app.config import get_settings
from app.paths import get_oa_profile_dir
from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.normalization import normalize_whitespace
from app.services.chrome_session import ChromeCDPSession, ChromeSessionError, inspect_chrome_environment
from app.services.credentials import credential_store
from app.sources.base import LoginExpiredError, NoticeSource, SourceError, SourceNotConfiguredError
from app.sources.generic import parse_configured_html


LOGIN_MARKERS = ("统一身份认证", "用户登录", "登录 oa", "login")
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "auth",
    "authorization",
    "jsessionid",
    "oauth_token",
    "session",
    "sessionid",
    "sid",
    "ticket",
    "token",
}


def sanitize_oa_url(value: str) -> str:
    """Remove credentials/tickets before a URL can enter SQLite or logs."""
    parts = urlsplit(value)
    query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in SENSITIVE_QUERY_KEYS
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


class OASource(NoticeSource):
    """Authenticated, Desktop-only OA adapter backed by a user-owned browser profile.

    The post-login DOM is deliberately configuration-driven. Until selectors are
    verified on a real authorized session the source reports ``unconfigured``
    rather than guessing a page structure or recording a crawler failure.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        settings = get_settings()
        self.profile_path = get_oa_profile_dir(settings.environment, settings.app_data_dir)
        self.parser_config = dict(config.get("parser_config") or {})
        sections = list(config.get("sections") or [])
        self.list_url = str(sections[0].get("url")) if sections else self.base_url
        self.login_url = str(config.get("login_url") or self.base_url)
        self.browser: ChromeCDPSession | None = None
        self.credential_ref = str(config.get("credential_ref") or "")
        self._cookies_restored = False
        self._source_urls: dict[str, str] = {}

    @staticmethod
    def ensure_runtime_available() -> None:
        environment = inspect_chrome_environment()
        if environment.error_code:
            raise SourceError(environment.error_code)

    async def _ensure_context(self, headless: bool | None = None) -> ChromeCDPSession:
        self.ensure_runtime_available()
        if self.browser is None:
            configured = get_settings().oa_headless if headless is None else headless
            self.browser = ChromeCDPSession(self.profile_path, headless=configured)
            try:
                await self.browser.start()
            except ChromeSessionError as exc:
                self.browser = None
                raise SourceError(str(exc)) from exc
        if not self._cookies_restored and self.credential_ref:
            secret = credential_store.load(self.credential_ref)
            if secret:
                try:
                    await self.browser.restore_cookies(json.loads(secret))
                except (TypeError, ValueError, ChromeSessionError) as exc:
                    raise SourceError("OA_SESSION_RESTORE_FAILED") from exc
            self._cookies_restored = True
        return self.browser

    @staticmethod
    def _looks_like_login(url: str, text: str) -> bool:
        lowered_url = url.lower()
        lowered_text = text.lower()
        return "/login" in lowered_url or any(marker in lowered_text for marker in LOGIN_MARKERS)

    async def _page_snapshot(
        self, url: str, *, headless: bool | None = None, wait_until: str = "domcontentloaded"
    ) -> tuple[str, str, str]:
        browser = await self._ensure_context(headless=headless)
        try:
            return await browser.navigate(url)
        except ChromeSessionError as exc:
            raise SourceError(str(exc)) from exc

    def _require_parser_configuration(self) -> None:
        required = ("item_selector", "title_selector", "link_selector", "content_selector")
        if any(not str(self.parser_config.get(key) or "").strip() for key in required):
            raise SourceNotConfiguredError("OA_PARSER_UNCONFIGURED")

    async def open_login_window(self) -> None:
        browser = await self._ensure_context(headless=False)
        try:
            await browser.navigate(self.login_url)
        except ChromeSessionError as exc:
            raise SourceError(str(exc)) from exc

    async def capture_session(self, reference: str) -> bool:
        browser = await self._ensure_context(headless=False)
        try:
            _, current, text = await browser.navigate(self.base_url)
            if self._looks_like_login(current, text):
                return False
            host = (urlsplit(self.base_url).hostname or "").lower()
            cookies = [
                cookie for cookie in await browser.cookies()
                if host == str(cookie.get("domain") or "").lstrip(".").lower()
                or host.endswith("." + str(cookie.get("domain") or "").lstrip(".").lower())
            ]
            if not cookies:
                raise SourceError("OA_SESSION_COOKIE_MISSING")
            credential_store.save(reference, json.dumps(cookies, ensure_ascii=False, separators=(",", ":")))
            self.credential_ref = reference
            return True
        except ChromeSessionError as exc:
            raise SourceError(str(exc)) from exc

    async def login_setup(self, timeout_seconds: float = 300) -> str:
        """Compatibility CLI flow; Desktop uses open_login_window + capture_session."""
        await self.open_login_window()
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            _, current, text = await self._page_snapshot(self.base_url, headless=False)
            if not self._looks_like_login(current, text):
                try:
                    self._require_parser_configuration()
                    items = await self.fetch_list()
                    if not items:
                        raise SourceNotConfiguredError("OA_LIST_SELECTOR_UNVERIFIED")
                    await self.fetch_detail(items[0])
                except SourceNotConfiguredError:
                    return "authenticated_unconfigured"
                return "ready"
            await asyncio.sleep(1)
        raise LoginExpiredError("OA_LOGIN_TIMEOUT")

    async def check_login(self) -> bool:
        _, current, text = await self._page_snapshot(self.base_url)
        return not self._looks_like_login(current, text)

    async def fetch_list(self) -> list[NoticeCandidate]:
        self._require_parser_configuration()
        html, final_url, text = await self._page_snapshot(self.list_url)
        if self._looks_like_login(final_url, text):
            raise LoginExpiredError("OA_LOGIN_EXPIRED")
        try:
            parsed = parse_configured_html(html, final_url, self.parser_config)
        except SourceError as exc:
            raise SourceNotConfiguredError("OA_LIST_SELECTOR_UNVERIFIED") from exc
        results: list[NoticeCandidate] = []
        for item in parsed[: get_settings().max_items_per_section]:
            safe_url = sanitize_oa_url(item.url)
            self._source_urls[safe_url] = item.url
            results.append(item.model_copy(update={"url": safe_url, "section": "校内通知"}))
        return results

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        self._require_parser_configuration()
        source_url = self._source_urls.get(notice.url, notice.url)
        html, final_url, text = await self._page_snapshot(source_url, wait_until="networkidle")
        if self._looks_like_login(final_url, text):
            raise LoginExpiredError("OA_LOGIN_EXPIRED")
        soup = BeautifulSoup(html, "html.parser")
        try:
            content_node = soup.select_one(str(self.parser_config["content_selector"]))
        except Exception as exc:
            raise SourceNotConfiguredError("OA_CONTENT_SELECTOR_INVALID") from exc
        if not isinstance(content_node, Tag):
            raise SourceNotConfiguredError("OA_CONTENT_SELECTOR_MISSING")
        content = normalize_whitespace(content_node.get_text("\n", strip=True))
        attachments: list[AttachmentData] = []
        attachment_selector = str(self.parser_config.get("attachment_selector") or "").strip()
        if attachment_selector:
            try:
                anchors = soup.select(attachment_selector)
            except Exception as exc:
                raise SourceNotConfiguredError("OA_ATTACHMENT_SELECTOR_INVALID") from exc
            for anchor in anchors[:50]:
                if not isinstance(anchor, Tag) or not anchor.get("href"):
                    continue
                raw_url = urljoin(final_url, str(anchor.get("href")))
                safe_url = sanitize_oa_url(raw_url)
                filename = normalize_whitespace(anchor.get_text(" ", strip=True))
                path = PurePosixPath(unquote(urlsplit(safe_url).path))
                filename = filename or path.name or "attachment"
                filename_suffix = PurePosixPath(filename).suffix
                attachments.append(
                    AttachmentData(
                        filename=filename,
                        url=safe_url,
                        type=(path.suffix or filename_suffix).removeprefix(".").lower() or "file",
                    )
                )
        return notice.model_copy(
            update={
                "url": sanitize_oa_url(final_url),
                "content": content,
                "attachments": attachments,
            }
        )

    async def close(self) -> None:
        if self.browser:
            await self.browser.close()
            self.browser = None


OaSource = OASource
