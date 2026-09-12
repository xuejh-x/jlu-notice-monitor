from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import PurePosixPath
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.dates import parse_date
from app.services.normalization import normalize_whitespace
from app.sources.base import SourceError, StaticHTMLSource


OA_NOTICE_CHANNEL_ID = "179577"
OA_ATTACHMENT_ENCODER_PATH = "/defaultroot/rd/download/BASEEncoderAjax.jsp"
OA_ATTACHMENT_DOWNLOAD_PATH = "/defaultroot/rd/download/attachdownload.jsp"
PINNED_PREFIX = re.compile(r"^\s*\[置顶\]\s*")


@dataclass(frozen=True)
class OAAttachmentReference:
    stored_name: str
    display_name: str
    information_id: str

    @property
    def encoder_value(self) -> str:
        return f"{self.stored_name}@{self.display_name}@{self.information_id}"


def _china_today() -> date:
    return datetime.now(timezone(timedelta(hours=8))).date()


def parse_oa_home_list_url(html: str, page_url: str) -> str:
    """Discover the public 校内通知 list from the OA home page."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".sub.xntz") or soup
    anchors = list(container.select("a.tz_more[href]"))
    anchors.extend(
        anchor
        for anchor in container.select("a[href]")
        if normalize_whitespace(anchor.get_text(" ", strip=True)).startswith("更多")
        and anchor not in anchors
    )
    for anchor in anchors:
        href = str(anchor.get("href") or "").strip()
        query = parse_qs(urlsplit(urljoin(page_url, href)).query)
        if query.get("channelId") == [OA_NOTICE_CHANNEL_ID]:
            return urljoin(page_url, href)
    raise SourceError("OA_PUBLIC_LIST_LINK_MISSING")


def _parse_oa_list_date(value: str, *, today: date | None = None) -> date | None:
    normalized = normalize_whitespace(value.replace("\xa0", " "))
    reference = today or _china_today()
    if normalized.startswith("今天"):
        return reference
    if normalized.startswith("昨天"):
        return reference - timedelta(days=1)
    if normalized.startswith("前天"):
        return reference - timedelta(days=2)
    return parse_date(normalized)


def _oa_notice_id(url: str) -> str | None:
    values = parse_qs(urlsplit(url).query).get("id")
    return values[0] if values and values[0].isdigit() else None


def parse_oa_list_html(
    html: str,
    page_url: str,
    *,
    today: date | None = None,
) -> list[NoticeCandidate]:
    """Parse list metadata only; detail bodies are deliberately not fetched here."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[NoticeCandidate] = []
    seen: set[str] = set()
    for row in soup.select("#itemContainer .li"):
        if not isinstance(row, Tag):
            continue
        title_anchor = row.select_one("a.font14[href*='getInformation.action']")
        if not isinstance(title_anchor, Tag):
            continue
        href = str(title_anchor.get("href") or "").strip()
        title = PINNED_PREFIX.sub(
            "", normalize_whitespace(title_anchor.get_text(" ", strip=True))
        )
        url = urljoin(page_url, href)
        notice_id = _oa_notice_id(url)
        if not title or not notice_id or url in seen:
            continue
        seen.add(url)
        publisher_node = row.select_one("a.column")
        time_node = row.select_one(".time")
        publisher = (
            normalize_whitespace(publisher_node.get_text(" ", strip=True))
            if isinstance(publisher_node, Tag)
            else None
        )
        published = (
            _parse_oa_list_date(time_node.get_text(" ", strip=True), today=today)
            if isinstance(time_node, Tag)
            else None
        )
        results.append(
            NoticeCandidate(
                public_id=f"oa-{notice_id}",
                title=title,
                url=url,
                publish_date=published,
                publisher=publisher or None,
                section="校内通知",
            )
        )
    return results


def parse_oa_attachment_references(html: str, page_url: str) -> list[OAAttachmentReference]:
    soup = BeautifulSoup(html, "html.parser")
    information_id = _oa_notice_id(page_url)
    if not information_id:
        return []
    results: list[OAAttachmentReference] = []
    seen: set[str] = set()
    for node in soup.select(".news_aboutFile span[onclick*='downloadthis']"):
        if not isinstance(node, Tag):
            continue
        stored_name = str(node.get("id") or "").strip()
        display_name = normalize_whitespace(
            str(node.get("title") or node.get_text(" ", strip=True))
        )
        if not stored_name or not display_name or stored_name in seen:
            continue
        seen.add(stored_name)
        results.append(
            OAAttachmentReference(
                stored_name=stored_name,
                display_name=display_name,
                information_id=information_id,
            )
        )
    return results


def parse_oa_detail_html(
    html: str,
    page_url: str,
    fallback: NoticeCandidate,
) -> NoticeCandidate:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one(".content_t")
    content_node = soup.select_one(".content_font.fontsize")
    metadata_node = soup.select_one(".content_time")
    if not isinstance(content_node, Tag):
        raise SourceError("OA_PUBLIC_DETAIL_CONTENT_MISSING")
    for unwanted in content_node.select("script, style, noscript"):
        unwanted.decompose()
    title = (
        normalize_whitespace(title_node.get_text(" ", strip=True))
        if isinstance(title_node, Tag)
        else fallback.title
    )
    content = normalize_whitespace(content_node.get_text("\n", strip=True))
    publish_date = fallback.publish_date
    publisher = fallback.publisher
    if isinstance(metadata_node, Tag):
        metadata = normalize_whitespace(metadata_node.get_text(" ", strip=True))
        match = re.search(r"20\d{2}年\d{1,2}月\d{1,2}日", metadata)
        if match:
            publish_date = parse_date(match.group(0)) or publish_date
        publisher_node = metadata_node.select_one("span")
        if isinstance(publisher_node, Tag):
            publisher = normalize_whitespace(publisher_node.get_text(" ", strip=True)) or publisher
    return fallback.model_copy(
        update={
            "title": title,
            "url": page_url,
            "publish_date": publish_date,
            "publisher": publisher,
            "content": content,
        }
    )


class OAPublicSource(StaticHTMLSource):
    """Official public OA 校内通知 adapter; no login, cookie, or browser session."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        sections = list(config.get("sections") or [])
        self.list_url = str(sections[0]["url"]) if sections else self.base_url

    def parse_list(self, html: str, page_url: str, section: str) -> list[NoticeCandidate]:
        return parse_oa_list_html(html, page_url)

    async def _attachment_url(
        self,
        reference: OAAttachmentReference,
        detail_url: str,
    ) -> str:
        encoder_url = urljoin(self.base_url, OA_ATTACHMENT_ENCODER_PATH)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.post(
                    encoder_url,
                    data={"res": reference.encoder_value},
                    headers={"Referer": detail_url},
                )
                response.raise_for_status()
                encoded = response.text.strip()
                if not encoded or "<" in encoded or len(encoded) > 4096:
                    raise SourceError("OA_PUBLIC_ATTACHMENT_ENCODING_INVALID")
                return urljoin(self.base_url, OA_ATTACHMENT_DOWNLOAD_PATH) + "?" + urlencode(
                    {"res": encoded}
                )
            except (httpx.HTTPError, UnicodeError, SourceError) as exc:
                last_error = exc
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff * (attempt + 1))
        raise SourceError(f"OA_PUBLIC_ATTACHMENT_URL_FAILED: {type(last_error).__name__}")

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        html = await self._get(notice.url)
        parsed = parse_oa_detail_html(html, notice.url, notice)
        attachments: list[AttachmentData] = []
        for reference in parse_oa_attachment_references(html, notice.url)[:50]:
            url = await self._attachment_url(reference, notice.url)
            suffix = PurePosixPath(reference.stored_name).suffix.lower().removeprefix(".")
            attachments.append(
                AttachmentData(
                    filename=reference.display_name,
                    url=url,
                    type=suffix or "file",
                )
            )
        return parsed.model_copy(update={"attachments": attachments})


OaPublicSource = OAPublicSource
