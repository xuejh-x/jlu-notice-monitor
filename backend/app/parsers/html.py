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
EXPLICIT_ATTACHMENT_EXTENSIONS = ARTICLE_EXTENSIONS | {".jpg", ".jpeg", ".png", ".gif", ".webp", ".rar", ".7z", ".ppt", ".pptx", ".csv", ".txt"}
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
    ".m-detail-content__container",
    ".v_news_content",
    "#vsb_content",
    ".article-content",
    ".article_content",
    ".news_content",
    ".content",
)

ARTICLE_PATH = re.compile(r"(?:^|/)info/[^/?#]+/[^/?#]+\.html?(?:[?#]|$)", re.I)
NAVIGATION_CLASS = re.compile(r"(?:^|[_-])(?:nav\d*|menu\d*|header|footer|breadcrumb|p_pages)(?:$|[_-])", re.I)


class HTMLParseError(ValueError):
    """An HTML response cannot safely be treated as notice content."""


def in_navigation(node: Tag) -> bool:
    for parent in (node, *node.parents):
        if not isinstance(parent, Tag):
            continue
        if parent.name in {"nav", "header", "footer"} or parent.get("role") == "navigation":
            return True
        labels = [str(parent.get("id") or ""), *parent.get("class", [])]
        if any(NAVIGATION_CLASS.search(label) for label in labels):
            return True
    return False


def usable_link(anchor: Tag, page_url: str) -> bool:
    href = str(anchor.get("href") or "").strip()
    if not href or in_navigation(anchor) or re.search(r"[<>\x00-\x20]", href):
        return False
    if href.lower().startswith(("javascript:", "mailto:", "#")):
        return False
    try:
        target = urlsplit(urljoin(page_url, href))
        return target.scheme in {"http", "https"} and bool(target.hostname) and not (target.username or target.password)
    except ValueError:
        return False


def validate_html_page(soup: BeautifulSoup) -> None:
    # Password forms and explicit error/verification headings are not notices.
    # Do not reject ordinary prose merely because it discusses login/errors.
    if soup.select_one("input[type='password']"):
        raise HTMLParseError("HTML_AUTH_REQUIRED: response contains a login form")
    for node in soup.select("title, h1"):
        label = normalize_whitespace(node.get_text(" ", strip=True))
        if label in {"系统提示", "权限提示", "访问受限"} and re.search(r"没有访问当前栏目的权限|无权访问当前栏目", soup.get_text(" ", strip=True)):
            raise HTMLParseError("HTML_PERMISSION_REQUIRED: response denies access to this column")
        if re.fullmatch(r"(?:40[034](?:\s*[-:：]?\s*(?:Not Found|Forbidden|错误|页面不存在))?|Not Found|Forbidden|Access Denied|用户登录|统一身份认证|统一身份认证平台|安全验证|访问验证|系统错误|出错了)", label, re.I):
            raise HTMLParseError("HTML_INTERSTITIAL: response is a login, error or verification page")


def is_empty_notice_list(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select(".p_t, .pb_sys_common, .news_list, .newslist, .list, .list3"):
        if in_navigation(node):
            continue
        label = normalize_whitespace(node.get_text(" ", strip=True))
        if re.search(r"共\s*0\s*条", label) or label in {"暂无通知", "暂无信息", "暂无数据", "没有相关信息"}:
            return True
    return False


def validate_detail_container(soup: BeautifulSoup, node: Tag, *, has_attachments: bool = False, page_url: str = "") -> None:
    validate_html_page(soup)
    if in_navigation(node) or any(in_navigation(a) for a in node.select("a[href]")) or node.select_one("nav, header, footer, [role='navigation']"):
        raise HTMLParseError("HTML_DETAIL_NAVIGATION: notice body contains site navigation")
    if not node.get_text(strip=True) and not has_attachments and not _extract_attachments(node, "https://attachment.invalid/"):
        if body_image_urls(node, page_url):
            return
        if node.select_one("img[src]"):
            raise HTMLParseError("HTML_DETAIL_IMAGE_ONLY_UNSUPPORTED: image notice has no extractable text; image support requires verification")
        raise HTMLParseError("HTML_DETAIL_EMPTY: no text or supported attachment in the notice container")


def _looks_like_article(anchor: Tag, text: str) -> bool:
    href = str(anchor.get("href") or "").strip()
    lowered = href.lower()
    if not text or lowered.startswith(("javascript:", "mailto:", "#")):
        return False
    if ARTICLE_PATH.search(lowered):
        return True
    # Other static CMS paths need a dated list row, not just a .htm suffix.
    row = anchor.find_parent(["li", "tr"])
    return bool(re.search(r"\.html?(?:[?#]|$)", lowered) and row
                and DATE_TEXT_PATTERN.search(row.get_text(" ", strip=True)))


def _list_title(anchor: Tag) -> str:
    if anchor.get("title"):
        return normalize_whitespace(str(anchor["title"]))
    node = anchor.select_one(".title, .news-title, .tit, .con > .span:first-child")
    return normalize_whitespace((node or anchor).get_text(" ", strip=True))


def _list_publish_date(row: Tag | None) -> date | None:
    if row is None:
        return None
    for node in row.select("time, .time, .date, .date1, .date-box"):
        if in_navigation(node):
            continue
        value = normalize_whitespace(str(node.get("datetime") or node.get_text(" ", strip=True)))
        # VSB calendar cards: day followed by year-month in a separate span.
        split = re.fullmatch(r"(\d{1,2})\s+(20\d{2})[-/.](\d{1,2})", value)
        if split:
            return parse_date(f"{split[2]}-{split[3]}-{split[1]}")
        return parse_date(value)  # Explicit invalid dates must not fall into prose.
    for node in row.select(":scope > span, :scope > a > span"):
        value = normalize_whitespace(node.get_text(" ", strip=True))
        if DATE_TEXT_PATTERN.fullmatch(value):
            return parse_date(value)
    copy = BeautifulSoup(str(row), "html.parser")
    for node in copy.select("a, .summary, .abstract, .info, .con"):
        node.decompose()
    return parse_date(copy.get_text(" ", strip=True))


def _detail_title(soup: BeautifulSoup, fallback: NoticeCandidate, content: Tag | None = None) -> str:
    selectors = (".m-detail-container__title", ".detail_head1", "form[name='_newscontent_fromname'] h2.tit",
                 "form[name='_newscontent_fromname'] h2[align='center']", ".nr_title", ".art-tit h3", ".detail-title", ".detail-tit h4",
                 "form[name='_newscontent_fromname'] > .bt", ".article-title", ".article_title", "h1", ".title")
    for selector in selectors:
        for node in soup.select(selector):
            if in_navigation(node) or node is content or (content is not None and content in node.parents):
                continue
            copy = BeautifulSoup(str(node), "html.parser")
            for child in list(copy.select("script, style, .meta, .article-meta")):
                child.decompose()
            if selector == ".nr_title":
                for child in list(copy.select("span")):
                    if re.match(r"^(?:作者|来源|时间|发布日期|发布时间|点击数)[：:]", child.get_text(strip=True)):
                        child.decompose()
            title = normalize_whitespace(copy.get_text(" ", strip=True))
            if selector in {"h1", ".title"} and not node.find_parent("form", attrs={"name": "_newscontent_fromname"}):
                prefix = fallback.title.rstrip(".… ")
                if not prefix or not (title.startswith(prefix) or prefix.startswith(title)):
                    continue
            if title and title not in {fallback.section, "通知公告", "学院通知", "校内通知", "学校概况", "教学通知", "网站首页"}:
                return title
    return fallback.title


def _detail_publish_date(soup: BeautifulSoup, content: Tag, fallback: date | None) -> date | None:
    # Only article metadata can override a list date. Body event/deadline dates
    # and a site's current-date clock cannot establish publication metadata.
    selectors = (".m-detail-container__info", ".meta", ".article-meta", ".article-info", ".news-info", ".sub", ".xiab",
                 ".detail-infor", ".detail-tit p", ".art-tit p", ".nr_title span", ".xq", ".conttime", ".title11 p",
                 ".content-bt-xia", ".title3 > p.ac", "time[datetime]",
                 "meta[property='article:published_time']", "meta[name='pubdate']")
    for selector in selectors:
        for node in soup.select(selector):
            if in_navigation(node) or node is content or content in node.parents or content in node.descendants:
                continue
            value = str(node.get("datetime") or node.get("content") or node.get_text(" ", strip=True))
            if selector.startswith(("time", "meta[")):
                published = parse_date(value)
            else:
                labels = r"创建时间" if selector == ".m-detail-container__info" else r"发布日期|发布时间|发表时间|日期|时间"
                match = re.search(r"(?<![\u4e00-\u9fff])(?:" + labels + r")[：:\s]*?(" + DATE_TEXT_PATTERN.pattern + ")", value)
                published = parse_date(match[1]) if match else None
            if published is not None:
                return published
    return fallback


def body_image_urls(node: Tag, page_url: str) -> list[str]:
    """Retain same-origin raster image references as inert plain text, not HTML."""
    urls: list[str] = []
    origin = urlsplit(page_url)
    for img in node.select("img[src]"):
        src = str(img.get("src") or "").strip()
        if in_navigation(img) or re.search(r"[<>\x00-\x20]", src):
            continue
        try:
            target = urlsplit(urljoin(page_url, src))
            if target.scheme not in {"http", "https"} or not target.hostname or target.username or target.password:
                continue
            if (target.scheme, target.hostname, target.port) != (origin.scheme, origin.hostname, origin.port):
                continue
            if PurePosixPath(unquote(target.path)).suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                continue
            if any(str(img.get(key) or "").isdigit() and int(img[key]) < 32 for key in ("width", "height")):
                continue
        except ValueError:
            continue
        url = target.geturl()
        if url not in urls:
            urls.append(url)
    return urls


def detail_plain_text(node: Tag, page_url: str) -> str:
    copy = BeautifulSoup(str(node), "html.parser")
    allowed = set(body_image_urls(node, page_url))
    seen: set[str] = set()
    for img in copy.select("img[src]"):
        url = urljoin(page_url, str(img["src"]).strip())
        if url in allowed and url not in seen:
            img.replace_with(url)
            seen.add(url)
        else:
            img.decompose()
    return normalize_whitespace(copy.get_text("\n", strip=True))


def parse_list_html(html: str, page_url: str, section: str | None = None) -> list[NoticeCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    validate_html_page(soup)
    if is_empty_notice_list(html):
        return []
    seen: set[str] = set()
    results: list[NoticeCandidate] = []
    anchors: list[Tag] = []
    for selector in LIST_SELECTORS:
        selected = [a for a in soup.select(selector) if usable_link(a, page_url)
                    and _looks_like_article(a, _list_title(a))]
        if selected:
            anchors = selected
            if any("info/" in str(a.get("href", "")) for a in selected):
                break
    for anchor in anchors:
        title = _list_title(anchor)
        href = str(anchor.get("href") or "").strip()
        if not _looks_like_article(anchor, title):
            continue
        url = urljoin(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        # VSB templates may put the date next to a title div inside the same
        # list/table row, not inside the anchor's immediate parent.
        row = anchor.find_parent(["li", "tr"]) or anchor.parent
        published = _list_publish_date(row)
        results.append(NoticeCandidate(title=title, url=url, publish_date=published, section=section))
    return results


def _select_content(soup: BeautifulSoup) -> Tag:
    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            return node
    raise HTMLParseError("HTML_DETAIL_UNSUPPORTED: no scoped notice content container; configure a content selector")


def _explicit_attachment(anchor: Tag) -> bool:
    if anchor.has_attr("download"):
        return True
    href = str(anchor.get("href") or "")
    if re.search(r"/system/_content/download\.jsp\?", href, re.I) and "news.DownloadAttachUrl" in href:
        return True
    if anchor.find_parent(class_=re.compile(r"^(?:attachments?|attach|news_aboutFile|m-detail-container__file)$", re.I)):
        return True
    row = anchor.find_parent("li")
    return bool(row and re.match(r"^附件\s*[【\[:：]", row.get_text(" ", strip=True)))


def _extract_attachments(node: Tag, page_url: str, *, explicit_only: bool = False) -> list[AttachmentData]:
    results: list[AttachmentData] = []
    seen: set[str] = set()
    for anchor in node.select("a[href]"):
        if not usable_link(anchor, page_url):
            continue
        explicit = _explicit_attachment(anchor)
        if explicit_only and not explicit:
            continue
        href = str(anchor.get("href") or "")
        url = urljoin(page_url, href)
        path = unquote(urlsplit(url).path)
        suffix = PurePosixPath(path).suffix.lower()
        text = normalize_whitespace(anchor.get_text(" ", strip=True))
        if anchor.find_parent(class_="m-detail-container__file"):
            # This CMS appends a display-only file size to the actual filename.
            text = re.sub(r"\s+-\s*\(\d+(?:\.\d+)?\s*[kmg]?B\)\s*$", "", text, flags=re.I)
        extensions = EXPLICIT_ATTACHMENT_EXTENSIONS if explicit else ARTICLE_EXTENSIONS
        filename_hint = str(anchor.get("download") or "") or text
        match = re.search(r"\.([a-z0-9]+)(?:[）)】\]\s]*$)", filename_hint, re.IGNORECASE)
        named_kind = f".{match.group(1).lower()}" if match else ""
        kind = suffix if suffix in extensions else (named_kind if named_kind in extensions else "")
        if not kind:
            kind = next((f".{m[1].lower()}" for m in re.finditer(r"\.([a-z0-9]+)(?:\?|$|\s)", url, re.I)
                         if f".{m[1].lower()}" in extensions), "")
        if not kind:
            continue
        if url in seen:
            continue
        seen.add(url)
        filename = text or str(anchor.get("download") or "") or PurePosixPath(path).name or f"attachment{kind}"
        results.append(AttachmentData(filename=filename, url=url, type=kind.lstrip(".")))
    return results


def detail_attachments(soup: BeautifulSoup, content: Tag, page_url: str) -> list[AttachmentData]:
    # Plain file links inside the article retain their existing behavior. Extra
    # types and links outside its body require explicit attachment evidence.
    scope = content.find_parent("form", attrs={"name": "_newscontent_fromname"}) or content.find_parent("article") or content.parent
    files = _extract_attachments(content, page_url)
    seen = {a.url for a in files}
    if isinstance(scope, Tag):
        for attachment in _extract_attachments(scope, page_url, explicit_only=True):
            if attachment.url not in seen:
                files.append(attachment)
                seen.add(attachment.url)
    return files


def parse_detail_html(html: str, page_url: str, fallback: NoticeCandidate) -> NoticeCandidate:
    soup = BeautifulSoup(html, "html.parser")
    validate_html_page(soup)
    content_node = _select_content(soup)
    title = _detail_title(soup, fallback, content_node)
    for unwanted in content_node.select("script, style, noscript"):
        unwanted.decompose()
    attachments = detail_attachments(soup, content_node, page_url)
    validate_detail_container(soup, content_node, has_attachments=bool(attachments), page_url=page_url)
    content = detail_plain_text(content_node, page_url)
    page_text = normalize_whitespace(soup.get_text(" ", strip=True))
    publish_date = _detail_publish_date(soup, content_node, fallback.publish_date)
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
        attachments=attachments,
        section=fallback.section,
    )
