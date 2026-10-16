from __future__ import annotations

import re
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.dates import parse_date
from app.services.normalization import normalize_whitespace

ARTICLE_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"}
EXPLICIT_ATTACHMENT_EXTENSIONS = ARTICLE_EXTENSIONS | {".jpg", ".jpeg", ".png", ".gif", ".webp", ".rar", ".7z", ".ppt", ".pptx", ".csv", ".txt", ".mp4"}
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
    ".article_details1 .cont > .text",
    ".v_news_content",
    "#vsb_content",
    ".article-content",
    ".article_content",
    ".news_content",
    "article.type-post > .entry-content",
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
        if label in {"系统提示", "权限提示", "访问受限"} and re.search(r"没有访问当前栏目的权限|无权访问当前栏目|无权访问此页面|没有访问此页面的权限", soup.get_text(" ", strip=True)):
            raise HTMLParseError("HTML_PERMISSION_REQUIRED: response denies access to this page or column")
        if re.fullmatch(r"(?:40[034](?:\s*[-:：]?\s*(?:Not Found|Forbidden|错误|页面不存在))?|Not Found|Forbidden|Access Denied|用户登录|统一身份认证|统一身份认证平台|安全验证|访问验证|系统错误|出错了)", label, re.I):
            raise HTMLParseError("HTML_INTERSTITIAL: response is a login, error or verification page")


def is_empty_notice_list(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    # Conflicting live article links make an empty marker inconclusive. Never
    # hide real notices because a footer or another widget says zero records.
    if any(usable_link(a, "https://empty.invalid/") and _looks_like_article(a, _list_title(a))
           for a in soup.select("a[href]")):
        return False
    for node in soup.select(".p_t, .pb_sys_common, .news_list, .newslist, .list, .list3"):
        if in_navigation(node):
            continue
        label = normalize_whitespace(node.get_text(" ", strip=True))
        if re.search(r"共\s*0\s*条", label) or label in {"暂无通知", "暂无信息", "暂无数据", "没有相关信息"}:
            return True
    for node in soup.select("#datalist > .empty-data"):
        if not in_navigation(node) and normalize_whitespace(node.get_text(" ", strip=True)) in {"暂无数据", "暂无信息", "暂无通知"}:
            return True
    for node in soup.select("td[id^='fanye']"):
        if not in_navigation(node) and re.fullmatch(r"共\s*0\s*条\s*0\s*/\s*0", normalize_whitespace(node.get_text(" ", strip=True))):
            if soup.select_one("input[name='urltype'][value='tree.TreeTempUrl']") and soup.select_one("script[src='/system/resource/js/gotopage.js']"):
                return True
    # VSB renders an empty UL beside a fully disabled first-page pager even
    # when it omits the visible record count. Require both template signals.
    for pager in soup.select(".pb_sys_common"):
        if in_navigation(pager) or not pager.select_one(".p_no_d") or pager.select_one("a[href]:not([href^='javascript:'])"):
            continue
        if pager.select_one(".p_no_d").get_text(strip=True) != "1":
            continue
        if not all(pager.select_one("." + name) for name in ["p_first_d", "p_prev_d", "p_next_d", "p_last_d"]):
            continue
        frames = [pager.parent, pager.parent.parent]
        if not any(frame.name not in {"body", "html", "[document]"} and not in_navigation(frame)
                   and any(not ul.get_text(strip=True) and not ul.select("a, li") for ul in frame.select("ul"))
                   for frame in frames):
            continue
        if soup.select_one("link[href*='/system/resource/css/pagedown/']"):
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


def _is_vsb_article_link(href: str) -> bool:
    if ARTICLE_PATH.search(href):
        return True
    try:
        parsed = urlsplit(href)
        values = parse_qs(parsed.query, keep_blank_values=True)
        return parsed.path.lower().endswith(".jsp") and values.get("urltype") == ["news.NewsContentUrl"] and all(
            len(values.get(name, [])) == 1 and re.fullmatch(r"[1-9]\d*", values[name][0])
            for name in ["wbtreeid", "wbnewsid"])
    except ValueError:
        return False


def _looks_like_article(anchor: Tag, text: str) -> bool:
    href = str(anchor.get("href") or "").strip()
    lowered = href.lower()
    if not text or lowered.startswith(("javascript:", "mailto:", "#")):
        return False
    if _is_vsb_article_link(href):
        return True
    # Other static CMS paths need a dated list row, not just a .htm suffix.
    row = anchor.find_parent(["li", "tr"])
    if row and any(a is not anchor and _is_vsb_article_link(str(a.get("href") or "")) for a in row.select("a[href]")):
        # VSB can place a section/tag link beside the actual dated article.
        # The date belongs to that article, not to the section link.
        return False
    return bool(re.search(r"\.html?(?:[?#]|$)", lowered) and row
                and DATE_TEXT_PATTERN.search(row.get_text(" ", strip=True)))


def _list_title(anchor: Tag) -> str:
    if anchor.get("title"):
        return normalize_whitespace(str(anchor["title"]))
    node = anchor.select_one(".title, .news-title, .tit, .con > .span:first-child")
    return normalize_whitespace((node or anchor).get_text(" ", strip=True))


def list_publication_date(value: str, *, label_text: str = "") -> date | None:
    """Preserve bare list dates, but never treat explicit update labels as publication."""
    labelled = label_text or value
    published = re.search(r"(?<![\u4e00-\u9fff])(?:发布日期|发布时间|发表时间)[：:\s]*(" + DATE_TEXT_PATTERN.pattern + ")", labelled)
    if published:
        return parse_date(published[1])
    if re.search(r"(?:更新时间|更新日期|修改时间|最后修改时间|最后更新时间)[：:\s]", labelled):
        return None
    return parse_date(value)


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
        return list_publication_date(value, label_text=node.get_text(" ", strip=True))  # Do not hide labels behind datetime attributes.
    for node in row.select(":scope > span, :scope > a > span"):
        value = normalize_whitespace(node.get_text(" ", strip=True))
        if DATE_TEXT_PATTERN.fullmatch(value):
            return parse_date(value)
    copy = BeautifulSoup(str(row), "html.parser")
    for node in copy.select("a, .summary, .abstract, .info, .con"):
        node.decompose()
    return list_publication_date(copy.get_text(" ", strip=True))


def _article_metadata_allowed(node: Tag, content: Tag | None) -> bool:
    if not in_navigation(node):
        return True
    # One observed VSB article template calls its heading block "nav01".
    # Keep ordinary navigation excluded; recognize only this inert, scoped
    # heading + publication layout before the same article's body.
    if content is None:
        return False
    article = content.find_parent("article", class_="type-post")
    if article is not None and content.parent is article:
        header = article.select_one(":scope > header.entry-header")
        if header is not None and (node is header or header in node.parents) and id(node) in {id(n) for n in content.previous_elements}:
            # An article header is semantic metadata, unlike the site's header.
            if (node.name == "h1" and "entry-title" in node.get("class", [])) or (node.name == "time" and node.has_attr("datetime")):
                return True
    frame = content.find_parent("form", attrs={"name": "_newscontent_fromname"})
    if frame is None:
        return False
    header = next((p for p in (node, *node.parents) if isinstance(p, Tag) and p.get("class") == ["nav01"]), None)
    return bool(header is not None and frame in header.parents and id(header) in {id(n) for n in content.previous_elements}
                and header.select_one(":scope > h3") and header.select_one(":scope > h6 .ll > span")
                and not header.select("a[href], nav, header, footer, [role='navigation']")
                and not any(isinstance(p, Tag) and (p.name in {"nav", "header", "footer"} or p.get("role") == "navigation") for p in header.parents))


def _detail_title(soup: BeautifulSoup, fallback: NoticeCandidate, content: Tag | None = None) -> str:
    before_body = {id(n) for n in content.previous_elements} if content is not None else None
    selectors = ("article.type-post > header.entry-header > h1.entry-title",
                 "form[name='_newscontent_fromname'] .content-bt", "form[name='_newscontent_fromname'] .t > p.ti",
                 "form[name='_newscontent_fromname'] .read > .readtitle", "form[name='_newscontent_fromname'] .content > #Title", "form[name='_newscontent_fromname'] .item_biaoti",
                 "form[name='_newscontent_fromname'] > p.biaoti", "form[name='_newscontent_fromname'] .nav01 > h3",
                 "form[name='_newscontent_fromname'] > .abouttitle > p",
                 ".right-nr:has(> .view-cnt > .v_news_content) > .view-title",
                 ".m-detail-container__title", ".article_details1 .cont > .title", "form[name='_newscontent_fromname'] .txt_title > h5",
                 "form[name='_newscontent_fromname'] .cont_con14_4_tit > h3", "form[name='_newscontent_fromname'] > .tittle",
                 "form[name='_newscontent_fromname'] .news_nr1", "form[name='_newscontent_fromname'] .tittle_con",
                 "form[name='_newscontent_fromname'] .title2", "form[name='_newscontent_fromname'] .tit", "form[name='_newscontent_fromname'] .cont_title",
                 "div:has(> #vsb_content) > h2", ".detail_head1", "form[name='_newscontent_fromname'] h2.tit",
                 "form[name='_newscontent_fromname'] h2[align='center']", ".nr_title", ".art-tit h3", ".detail-title", ".detail-tit h4",
                 "form[name='_newscontent_fromname'] > .bt", ".article-title", ".article_title", "h1", ".title")
    for selector in selectors:
        for node in soup.select(selector):
            if not _article_metadata_allowed(node, content) or node is content or (content is not None and (content in node.parents or content in node.descendants or id(node) not in before_body)):
                continue
            copy = BeautifulSoup(str(node), "html.parser")
            for child in list(copy.select("script, style, .meta, .article-meta")):
                child.decompose()
            if selector == ".nr_title":
                for child in list(copy.select("span")):
                    if re.match(r"^(?:作者|来源|时间|发布日期|发布时间|点击数)[：:]", child.get_text(strip=True)):
                        child.decompose()
            title = normalize_whitespace(copy.get_text(" ", strip=True))
            if re.match(r"^(?:上一[篇条]|下一[篇条])[：:\s]", title):
                continue
            if selector in {"h1", ".title"} and not node.find_parent("form", attrs={"name": "_newscontent_fromname"}):
                prefix = fallback.title.rstrip(".… ")
                if not prefix or not (title.startswith(prefix) or prefix.startswith(title)):
                    continue
            if title and title not in {fallback.section, "通知公告", "学院通知", "校内通知", "学校概况", "教学通知", "网站首页"}:
                return title
    # Unknown VSB header layouts can use h3/h5 rather than the named classes.
    # Only accept a heading in this article's frame, before its body, and
    # corroborated by the list prefix or the document title.
    frame = content.find_parent("form", attrs={"name": "_newscontent_fromname"}) if content else None
    if frame is None and content:
        frame = content.find_parent(class_="neirong")
    if frame is not None and content is not None:
        before = {id(n) for n in content.previous_elements}
        document_title = normalize_whitespace(soup.title.get_text(" ", strip=True)) if soup.title else ""
        prefix = fallback.title.rstrip(".… ")
        for node in frame.select("h1,h2,h3,h4,h5,h6"):
            if id(node) not in before or not _article_metadata_allowed(node, content) or content in node.parents or content in node.descendants:
                continue
            title = normalize_whitespace(node.get_text(" ", strip=True))
            if title and ((prefix and title.startswith(prefix)) or document_title.startswith(title)):
                return title
    return fallback.title


def _detail_publish_date(soup: BeautifulSoup, content: Tag, fallback: date | None) -> date | None:
    # Only article metadata can override a list date. Body event/deadline dates
    # and a site's current-date clock cannot establish publication metadata.
    selectors = ("form[name='_newscontent_fromname'] > div > h1 + div[align='center']",
                 "table:has(> tr > td.content > #vsb_content) > tr > td.pubtime_publisher",
                 "article.type-post > header.entry-header time.entry-date[datetime]",
                 "form[name='_newscontent_fromname'] > .wzxxys", "form[name='_newscontent_fromname'] .nav01 > h6 .ll > span",
                 "form[name='_newscontent_fromname'] > h3 > span", ".right-nr:has(> .view-cnt > .v_news_content) > .view-info",
                 ".m-detail-container__info", ".article_details1 .liner", "form[name='_newscontent_fromname'] .cont_con14_4_tit > p",
                 "form[name='_newscontent_fromname'] > .pe_data", "form[name='_newscontent_fromname'] .txt_title > span",
                 "form[name='_newscontent_fromname'] .zzly", "form[name='_newscontent_fromname'] .info",
                 "div:has(> #vsb_content) > h3.info",
                 ".meta", ".article-meta", ".article-info", ".news-info", ".sub", ".xiab",
                 ".detail-infor", ".detail-tit p", ".art-tit p", ".nr_title span", ".xq", ".conttime", ".title11 p",
                 ".content-bt-xia", ".title3 > p.ac", "time[datetime]",
                 "meta[property='article:published_time']", "meta[name='pubdate']")
    before_body = {id(n) for n in content.previous_elements}
    for selector in selectors:
        for node in soup.select(selector):
            if not _article_metadata_allowed(node, content) or node is content or content in node.parents or content in node.descendants or (selector in selectors[:7] and id(node) not in before_body):
                continue
            value = str(node.get("datetime") or node.get("content") or node.get_text(" ", strip=True))
            if (node.name == "time" and node.has_attr("datetime")) or selector.startswith("meta["):
                published = parse_date(value)
            else:
                labels = r"创建时间" if selector == ".m-detail-container__info" else r"发布日期|发布时间|发表时间|日期|时间"
                match = re.search(r"(?<![\u4e00-\u9fff])(?:" + labels + r")[：:\s]*?(" + DATE_TEXT_PATTERN.pattern + ")", value)
                published = parse_date(match[1]) if match else None
            if published is not None:
                return published
    # These two observed metadata cells use a bare date. Require an exact
    # date-only value before the body and reject conflicting header dates.
    before_body = {id(n) for n in content.previous_elements}
    bare_dates = set()
    for node in soup.select("form[name='_newscontent_fromname'] > .t > .author > span, form[name='_newscontent_fromname'] .xiab > .xb1"):
        if id(node) not in before_body or not _article_metadata_allowed(node, content):
            continue
        value = normalize_whitespace(node.get_text(" ", strip=True))
        if DATE_TEXT_PATTERN.fullmatch(value):
            parsed = parse_date(value)
            if parsed:
                bare_dates.add(parsed)
    if len(bare_dates) == 1:
        return next(iter(bare_dates))
    # A VSB article header may have no stable metadata class. Read only short
    # labelled nodes before the body inside the article frame, never prose or
    # the page clock. Conflicting dates remain unconfirmed.
    frame = content.find_parent("form", attrs={"name": "_newscontent_fromname"}) or content.find_parent(class_="neirong")
    if frame is not None:
        before = {id(n) for n in content.previous_elements}
        dates = set()
        for node in frame.select("div,p,span,i,h2,h3,h4,h5,h6"):
            if id(node) not in before or in_navigation(node) or node is content or content in node.parents or content in node.descendants:
                continue
            value = normalize_whitespace(node.get_text(" ", strip=True))
            if len(value) > 300:
                continue
            match = re.search(r"(?<![\u4e00-\u9fff])(?:发布日期|发布时间|发表时间|发表于|日期)[：:\s]*(" + DATE_TEXT_PATTERN.pattern + ")", value)
            if match:
                parsed = parse_date(match[1])
                if parsed:
                    dates.add(parsed)
        if len(dates) == 1:
            return next(iter(dates))
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


def _embedded_pdf_attachments(content: Tag, page_url: str) -> list[AttachmentData]:
    """Retain literal same-origin VSB PDF references; never execute scripts."""
    origin = urlsplit(page_url)
    attachments = []
    for script in content.select("script:not([src])"):
        for match in re.finditer(r"(?:^|[;\s])showVsbpdfIframe\(\s*['\"]([^'\"\\\r\n]+)['\"]\s*,", script.get_text()):
            href = match[1]
            if re.search(r"[<>\x00-\x20]", href):
                continue
            try:
                target = urlsplit(urljoin(page_url, href))
                if target.scheme not in {"http", "https"} or target.username or target.password:
                    continue
                if (target.scheme, target.hostname, target.port) != (origin.scheme, origin.hostname, origin.port):
                    continue
                path = PurePosixPath(unquote(target.path))
                if path.suffix.lower() != ".pdf":
                    continue
            except ValueError:
                continue
            attachments.append(AttachmentData(filename=path.name, url=target.geturl(), type="pdf"))
            if len(attachments) == 50:
                return attachments
    return attachments


def detail_attachments(soup: BeautifulSoup, content: Tag, page_url: str) -> list[AttachmentData]:
    # Plain file links inside the article retain their existing behavior. Extra
    # types and links outside its body require explicit attachment evidence.
    scope = content.find_parent("form", attrs={"name": "_newscontent_fromname"}) or content.find_parent("article") or content.parent
    files = _extract_attachments(content, page_url)
    seen = {a.url for a in files}
    article = content.find_parent("article", class_="type-post")
    if article is not None and content.parent is article:
        for footer in article.select(":scope > footer"):
            heading = footer.select_one(":scope > h4")
            listing = footer.select_one(":scope > ul:not(.tag-list)")
            if heading is None or listing is None or not re.fullmatch(r"相关附件[：:]\s*\d+", normalize_whitespace(heading.get_text(" ", strip=True))):
                continue
            # Only the labelled article attachment list is a file scope. Site
            # footers and tag/category links remain excluded by usable_link.
            copy = BeautifulSoup(str(listing), "html.parser")
            for attachment in _extract_attachments(copy, page_url):
                if attachment.url not in seen:
                    files.append(attachment)
                    seen.add(attachment.url)
    for attachment in _embedded_pdf_attachments(content, page_url):
        if attachment.url not in seen:
            files.append(attachment)
            seen.add(attachment.url)
    if isinstance(scope, Tag):
        for attachment in _extract_attachments(scope, page_url, explicit_only=True):
            if attachment.url not in seen:
                files.append(attachment)
                seen.add(attachment.url)
    return files


def attachment_snapshot_complete(soup: BeautifulSoup, content: Tag, attachments: list[AttachmentData], page_url: str) -> bool:
    """Only recognized static article scopes authorize removal of owned refs.

    Heuristic containers, dynamic embeds, unsupported explicit file entries and
    capped results remain partial. This says nothing about file availability.
    """
    scope = content.find_parent("form", attrs={"name": "_newscontent_fromname"}) or content.find_parent("article", class_="type-post")
    if not isinstance(scope, Tag) or len(attachments) >= 50:
        return False
    if scope.select("script, iframe, object, embed, [onclick]"):
        return False
    known = {item.url for item in attachments}
    for anchor in scope.select("a[href]"):
        href = str(anchor.get("href") or "")
        if href.lower().startswith("javascript:"):
            return False
    # A recognized body scope is insufficient when the page also exposes an
    # unextracted file, including a file kind outside the generic body whitelist
    # or an attachment widget outside the CMS form. Retain prior references.
    for anchor in soup.select("a[href], a[download]"):
        href = str(anchor.get("href") or "")
        try:
            target_url = urljoin(page_url, href)
            path_kind = PurePosixPath(unquote(urlsplit(target_url).path)).suffix.lower()
        except ValueError:
            return False
        name_hint = str(anchor.get("download") or "") or anchor.get_text(" ", strip=True)
        name_kind = PurePosixPath(name_hint).suffix.lower()
        file_hint = path_kind in EXPLICIT_ATTACHMENT_EXTENSIONS or name_kind in EXPLICIT_ATTACHMENT_EXTENSIONS
        if (_explicit_attachment(anchor) or anchor.has_attr("download") or file_hint) and target_url not in known:
            return False
    return True


def parse_detail_html(html: str, page_url: str, fallback: NoticeCandidate) -> NoticeCandidate:
    soup = BeautifulSoup(html, "html.parser")
    validate_html_page(soup)
    content_node = _select_content(soup)
    title = _detail_title(soup, fallback, content_node)
    attachments = detail_attachments(soup, content_node, page_url)
    complete = attachment_snapshot_complete(soup, content_node, attachments, page_url)
    for unwanted in content_node.select("script, style, noscript"):
        unwanted.decompose()
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
        attachments_complete=complete,
        section=fallback.section,
    )
