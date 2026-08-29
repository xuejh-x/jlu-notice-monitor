from __future__ import annotations

import re
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.dates import parse_date
from app.services.normalization import normalize_whitespace

ARTICLE_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"}
DATE_TEXT_PATTERN = re.compile(r"20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}日?")
LIST_SELECTORS = (
    ".list li a",
    ".news_list li a",
    ".newslist li a",
    ".list-box li a",
    ".right_list li a",
    "ul li a",
)
CONTENT_SELECTORS = (
    ".v_news_content",
    "#vsb_content",
    ".article-content",
    ".article_content",
    ".news_content",
    ".content",
)


def _looks_like_article(href: str, text: str, require_info_path: bool = False) -> bool:
    lowered = href.lower()
    if not text or lowered.startswith(("javascript:", "mailto:", "#")):
        return False
    if require_info_path:
        return "info/" in lowered
    return "info/" in lowered or lowered.endswith((".htm", ".html"))


def parse_list_html(html: str, page_url: str, section: str | None = None) -> list[NoticeCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    results: list[NoticeCandidate] = []
    anchors: list[Tag] = []
    for selector in LIST_SELECTORS:
        selected = soup.select(selector)
        if selected:
            anchors = selected
            if any("info/" in str(a.get("href", "")) for a in selected):
                break
    require_info_path = any("info/" in str(anchor.get("href", "")) for anchor in anchors)
    for anchor in anchors:
        title = normalize_whitespace(anchor.get("title") or anchor.get_text(" ", strip=True))
        href = str(anchor.get("href") or "").strip()
        if not _looks_like_article(href, title, require_info_path):
            continue
        url = urljoin(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        parent_text = anchor.parent.get_text(" ", strip=True) if anchor.parent else ""
        date_match = DATE_TEXT_PATTERN.search(parent_text)
        published = parse_date(date_match.group(0)) if date_match else None
        results.append(NoticeCandidate(title=title, url=url, publish_date=published, section=section))
    return results


def _select_content(soup: BeautifulSoup) -> Tag:
    first_known: Tag | None = None
    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            first_known = first_known or node
            if len(node.get_text(strip=True)) >= 20:
                return node
    if first_known is not None:
        return first_known
    return soup.body or soup


def _extract_attachments(node: Tag, page_url: str) -> list[AttachmentData]:
    results: list[AttachmentData] = []
    seen: set[str] = set()
    for anchor in node.select("a[href]"):
        href = str(anchor.get("href") or "")
        url = urljoin(page_url, href)
        path = unquote(urlsplit(url).path)
        suffix = PurePosixPath(path).suffix.lower()
        text = normalize_whitespace(anchor.get_text(" ", strip=True))
        match = re.search(r"\.(pdf|docx?|xlsx?|zip)(?:\?|$|\s)", f"{url} {text}", re.IGNORECASE)
        kind = suffix if suffix in ARTICLE_EXTENSIONS else (f".{match.group(1).lower()}" if match else "")
        if not kind:
            continue
        if url in seen:
            continue
        seen.add(url)
        filename = text or PurePosixPath(path).name or f"attachment{kind}"
        results.append(AttachmentData(filename=filename, url=url, type=kind.lstrip(".")))
    return results


def parse_detail_html(html: str, page_url: str, fallback: NoticeCandidate) -> NoticeCandidate:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("h1") or soup.select_one(".article-title") or soup.select_one(".title")
    title = normalize_whitespace(title_node.get_text(" ", strip=True)) if title_node else fallback.title
    content_node = _select_content(soup)
    for unwanted in content_node.select("script, style, noscript"):
        unwanted.decompose()
    content = normalize_whitespace(content_node.get_text("\n", strip=True))
    page_text = normalize_whitespace(soup.get_text(" ", strip=True))
    publish_date = fallback.publish_date
    for pattern in (
        r"发布日期[：:]?\s*(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}日?)",
        r"发布时间[：:]?\s*(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}日?)",
        r"(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}日?)",
    ):
        match = re.search(pattern, page_text)
        if match:
            publish_date = parse_date(match.group(1)) or publish_date
            break
    publisher_match = re.search(r"(?:来源|发布人|作者)[：:]?\s*([^\s]{2,30})", page_text)
    publisher = publisher_match.group(1) if publisher_match else fallback.publisher
    if publisher and any(marker in publisher for marker in ("发布日期", "发布时间", "点击")):
        publisher = fallback.publisher
    return NoticeCandidate(
        title=title,
        url=page_url,
        publish_date=publish_date,
        publisher=publisher,
        content=content,
        attachments=_extract_attachments(soup, page_url),
        section=fallback.section,
    )
