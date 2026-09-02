from __future__ import annotations

import asyncio
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup, Tag
import httpx

from app.config import get_settings, load_yaml
from app.parsers import parse_detail_html, parse_list_html
from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.dates import parse_date
from app.services.normalization import normalize_whitespace
from app.services.source_security import UnsafeSourceUrl, validate_peer_address, validate_source_url
from app.sources.base import LoginExpiredError, NoticeSource, SourceError


class SafeFetcher:
    def __init__(
        self,
        *,
        allow_private_network: bool = False,
        validation_scope: Literal["local", "cloud"] = "local",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        crawler = load_yaml("settings.yaml").get("crawler", {})
        self.allow_private_network = allow_private_network
        self.validation_scope = validation_scope
        self.max_bytes = settings.source_max_response_bytes
        self.max_redirects = 3
        self.retries = int(crawler.get("retries", 2))
        self.backoff = float(crawler.get("retry_backoff_seconds", 1.0))
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout,
            follow_redirects=False,
            headers={"User-Agent": str(crawler.get("user_agent", "NoticeHub/0.5"))},
            transport=transport,
            trust_env=validation_scope == "local",
        )
        self.auth_required = False
        self.login_url: str | None = None

    async def get(self, url: str) -> tuple[str, str, str]:
        current = url
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                for _ in range(self.max_redirects + 1):
                    await self.validate_url(current)
                    async with self.client.stream("GET", current) as response:
                        network_stream = response.extensions.get("network_stream")
                        peer = (
                            network_stream.get_extra_info("server_addr")
                            if network_stream is not None and hasattr(network_stream, "get_extra_info")
                            else None
                        )
                        if self.validation_scope == "cloud":
                            validate_peer_address(peer, allow_private_network=self.allow_private_network)
                        if self.auth_required and response.status_code in {401, 403}:
                            raise LoginExpiredError("AUTH_SESSION_EXPIRED")
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise SourceError("Redirect response did not include a location")
                            current = urljoin(current, location)
                            if self.auth_required and self.login_url:
                                login_host_path = urlsplit(self.login_url)
                                target = urlsplit(current)
                                if (target.hostname, target.path.rstrip("/")) == (
                                    login_host_path.hostname,
                                    login_host_path.path.rstrip("/"),
                                ):
                                    raise LoginExpiredError("AUTH_SESSION_EXPIRED")
                            continue
                        response.raise_for_status()
                        declared = int(response.headers.get("content-length", "0") or 0)
                        if declared > self.max_bytes:
                            raise SourceError("Source response exceeds the configured size limit")
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > self.max_bytes:
                                raise SourceError("Source response exceeds the configured size limit")
                        encoding = response.encoding or "utf-8"
                        return body.decode(encoding, errors="replace"), response.headers.get("content-type", ""), str(response.url)
                raise SourceError("Source exceeded the redirect limit")
            except LoginExpiredError:
                raise
            except (httpx.HTTPError, UnicodeError, SourceError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff * (attempt + 1))
        raise SourceError(f"Source request failed: {last_error}")

    async def validate_url(self, url: str) -> str:
        return await validate_source_url(
            url,
            allow_private_network=self.allow_private_network,
            validation_scope=self.validation_scope,
        )

    async def close(self) -> None:
        await self.client.aclose()


def _rss_date(value: str | None) -> date | None:
    if not value:
        return None
    parsed = parse_date(value)
    if parsed:
        return parsed
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, OverflowError):
        return None


def parse_rss_atom(text: str, page_url: str) -> list[NoticeCandidate]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise SourceError("The URL is not a valid RSS or Atom feed") from exc
    results: list[NoticeCandidate] = []
    if root.tag.lower().endswith("rss") or root.find("channel") is not None:
        found_channel = root.find("channel")
        channel = found_channel if found_channel is not None else root
        for item in channel.findall("item"):
            title = normalize_whitespace(item.findtext("title") or "")
            link = normalize_whitespace(item.findtext("link") or "")
            if not title or not link:
                continue
            description = normalize_whitespace(item.findtext("description") or "")
            results.append(NoticeCandidate(title=title, url=urljoin(page_url, link), publish_date=_rss_date(item.findtext("pubDate")), content=BeautifulSoup(description, "html.parser").get_text("\n", strip=True)))
    else:
        namespace = "{http://www.w3.org/2005/Atom}"
        entries = root.findall(f"{namespace}entry") or root.findall("entry")
        for entry in entries:
            title = normalize_whitespace(entry.findtext(f"{namespace}title") or entry.findtext("title") or "")
            link_node = entry.find(f"{namespace}link") or entry.find("link")
            link = str(link_node.get("href") or "") if link_node is not None else ""
            content = entry.findtext(f"{namespace}content") or entry.findtext(f"{namespace}summary") or ""
            published = entry.findtext(f"{namespace}published") or entry.findtext(f"{namespace}updated")
            if title and link:
                results.append(NoticeCandidate(title=title, url=urljoin(page_url, link), publish_date=_rss_date(published), content=BeautifulSoup(content, "html.parser").get_text("\n", strip=True)))
    if not results:
        raise SourceError("No notices were found in the RSS or Atom feed")
    return results


def parse_configured_html(text: str, page_url: str, config: dict[str, Any]) -> list[NoticeCandidate]:
    item_selector = str(config.get("item_selector", "")).strip()
    if not item_selector:
        return parse_list_html(text, page_url)
    soup = BeautifulSoup(text, "html.parser")
    try:
        items = soup.select(item_selector)
    except Exception as exc:
        raise SourceError("The item selector is invalid") from exc
    results: list[NoticeCandidate] = []
    for node in items:
        if not isinstance(node, Tag):
            continue
        try:
            title_node = node.select_one(str(config.get("title_selector") or "a"))
            link_node = node.select_one(str(config.get("link_selector") or "a"))
            date_node = node.select_one(str(config.get("date_selector"))) if config.get("date_selector") else None
        except Exception as exc:
            raise SourceError("One or more advanced selectors are invalid") from exc
        if not isinstance(title_node, Tag) or not isinstance(link_node, Tag):
            continue
        title = normalize_whitespace(title_node.get_text(" ", strip=True))
        href = str(link_node.get("href") or "").strip()
        if title and href:
            results.append(NoticeCandidate(title=title, url=urljoin(page_url, href), publish_date=parse_date(date_node.get_text(" ", strip=True)) if isinstance(date_node, Tag) else None))
    if not results:
        raise SourceError("The configured selectors did not find any notices")
    return results


class GenericPublicSource(NoticeSource):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.parser_config = dict(config.get("parser_config") or {})
        self.fetcher = SafeFetcher(
            allow_private_network=bool(config.get("allow_private_network", False)),
            validation_scope=str(config.get("validation_scope", "local")),
        )
        self.detected_type = str(config.get("content_parser", config.get("parser", "auto")))

    async def fetch_list(self) -> list[NoticeCandidate]:
        text, content_type, final_url = await self.fetcher.get(self.base_url)
        looks_feed = "xml" in content_type.lower() or text.lstrip().startswith("<?xml") or "<rss" in text[:500].lower() or "<feed" in text[:500].lower()
        if self.detected_type in {"rss", "atom"} or (self.detected_type == "auto" and looks_feed):
            self.detected_type = "rss"
            parsed_feed = parse_rss_atom(text, final_url)[: get_settings().max_items_per_section]
            return await self._safe_items(parsed_feed)
        self.detected_type = "generic_html"
        results: list[NoticeCandidate] = []
        seen_urls: set[str] = set()
        page_text, page_url = text, final_url
        limit = min(
            int(self.parser_config.get("pagination_limit", 1)),
            get_settings().source_max_pages,
        )
        for _ in range(limit):
            parsed = parse_configured_html(page_text, page_url, self.parser_config)
            for item in parsed:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    results.append(item)
            next_selector = str(self.parser_config.get("next_page_selector", "")).strip()
            if not next_selector:
                break
            soup = BeautifulSoup(page_text, "html.parser")
            try:
                next_node = soup.select_one(next_selector)
            except Exception as exc:
                raise SourceError("The next-page selector is invalid") from exc
            if not isinstance(next_node, Tag) or not next_node.get("href"):
                break
            next_url = urljoin(page_url, str(next_node.get("href")))
            if next_url == page_url:
                break
            page_text, _, page_url = await self.fetcher.get(next_url)
        if not results:
            raise SourceError("This page is unsupported or needs advanced selector configuration")
        return await self._safe_items(results[: get_settings().max_items_per_section])

    async def _safe_items(self, items: list[NoticeCandidate]) -> list[NoticeCandidate]:
        safe: list[NoticeCandidate] = []
        for item in items:
            try:
                await self.fetcher.validate_url(item.url)
            except UnsafeSourceUrl:
                continue
            safe.append(item)
        if not safe:
            raise SourceError("All detected notice links were rejected by URL security policy")
        return safe

    async def _safe_attachments(self, attachments: list[AttachmentData]) -> list[AttachmentData]:
        safe: list[AttachmentData] = []
        for attachment in attachments[:50]:
            try:
                await self.fetcher.validate_url(attachment.url)
            except UnsafeSourceUrl:
                continue
            safe.append(attachment)
        return safe

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        if notice.content:
            return notice
        text, _, final_url = await self.fetcher.get(notice.url)
        configured = str(self.parser_config.get("content_selector", "")).strip()
        if not configured:
            parsed = parse_detail_html(text, final_url, notice)
            return parsed.model_copy(update={"attachments": await self._safe_attachments(parsed.attachments)})
        soup = BeautifulSoup(text, "html.parser")
        try:
            node = soup.select_one(configured)
        except Exception as exc:
            raise SourceError("The detail content selector is invalid") from exc
        if not isinstance(node, Tag):
            raise SourceError("The detail content selector did not match")
        content = normalize_whitespace(node.get_text("\n", strip=True))
        attachments: list[AttachmentData] = []
        attachment_selector = str(self.parser_config.get("attachment_selector", "")).strip()
        if attachment_selector:
            try:
                anchors = soup.select(attachment_selector)
            except Exception as exc:
                raise SourceError("The attachment selector is invalid") from exc
            for anchor in anchors:
                if isinstance(anchor, Tag) and anchor.get("href"):
                    url = urljoin(final_url, str(anchor.get("href")))
                    filename = normalize_whitespace(anchor.get_text(" ", strip=True)) or url.rsplit("/", 1)[-1]
                    attachments.append(AttachmentData(filename=filename, url=url, type=filename.rsplit(".", 1)[-1].lower() if "." in filename else "file"))
        return notice.model_copy(update={"url": final_url, "content": content, "attachments": await self._safe_attachments(attachments)})

    async def close(self) -> None:
        await self.fetcher.close()


class AuthenticatedHTTPSource(GenericPublicSource):
    """Local-only HTTP authentication adapter; secrets never enter source config responses."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        from app.services.credentials import credential_store

        reference = str(config.get("credential_ref") or "")
        secret = credential_store.load(reference) if reference else None
        if not secret:
            raise SourceError("AUTH_CREDENTIAL_UNAVAILABLE")
        auth_type = str(config.get("auth_type") or "")
        self.fetcher.auth_required = True
        self.fetcher.login_url = str(config.get("login_url") or "") or None
        if auth_type == "basic":
            import base64

            username = str(config.get("auth_username") or "")
            token = base64.b64encode(f"{username}:{secret}".encode("utf-8")).decode("ascii")
            self.fetcher.client.headers["Authorization"] = f"Basic {token}"
        elif auth_type in {"bearer", "api_token"}:
            self.fetcher.client.headers["Authorization"] = f"Bearer {secret}"
        elif auth_type == "cookie":
            self.fetcher.client.headers["Cookie"] = secret
        else:
            raise SourceError("AUTH_TYPE_REQUIRES_INTERACTIVE_LOGIN")
