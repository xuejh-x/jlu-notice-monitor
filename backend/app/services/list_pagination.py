"""Opt-in list bounds for observed links and a verified public GET-form template."""
from pathlib import PurePosixPath
import posixpath
import re
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from app.services.normalization import canonicalize_url

PAGE_PARAMS = {"page", "p", "pageno", "pagenum", "pageindex", "page_no", "page_num", "page_index", "pagesize", "page_size", "offset", "start", "current"}


def _page_key(url):
    parsed = urlsplit(url)
    return urlunsplit(parsed._replace(query=urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True))), fragment=""))


def _origin(parsed):
    return parsed.scheme.lower(), parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


def _observed_get_form(soup, node, page_url):
    """Recognize one observed public CMS template without executing JavaScript."""
    call = re.fullmatch(r"page\(\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*['\"]['\"]\s*)?\);?", str(node.get("onclick") or "").strip())
    if not call or not (1 <= int(call[1]) <= 100000 and 1 <= int(call[2]) <= 100):
        return None
    code = re.sub(r"\s+", "", "\n".join(n.get_text() for n in soup.select("script:not([src])"))).replace("'", '"')
    known = 'functionpage(n,s){$("#pageNo").val(n);$("#pageSize").val(s);$("#searchForm").submit();returnfalse;}'
    if known not in code or code.count("functionpage(") != 1:
        return None
    forms = soup.select("form#searchForm")
    if len(forms) != 1 or str(forms[0].get("method", "get")).casefold() != "get":
        return None
    form = forms[0]
    if form.select("input[type=password],input[type=file],textarea,select"):
        return None
    fields = []
    for control in form.select("input[name]"):
        kind = str(control.get("type", "text")).casefold()
        if control.has_attr("disabled") or kind in {"button", "submit", "reset"}:
            continue
        if kind not in {"hidden", "text", "search"}:
            return None
        name = str(control["name"])
        if name not in {"cid", "pageNo", "pageSize", "keyword"}:
            return None
        value = str(control.get("value") or "")
        if name in {"pageNo", "pageSize"}:
            if control.get("id") != name or kind != "hidden":
                return None
            value = call[1] if name == "pageNo" else call[2]
        fields.append((name, value))
    if any(sum(k == field for k, _ in fields) != 1 for field in ["cid", "pageNo", "pageSize"]):
        return None
    target = urlsplit(urljoin(page_url, str(form.get("action") or page_url)))
    return urlunsplit(target._replace(query=urlencode(parse_qsl(target.query, keep_blank_values=True) + fields), fragment=""))


class ListPagination:
    def __init__(self, start_url, config, *, max_pages, items_per_section):
        self.start_url = start_url
        self.selector = str(config.get("next_page_selector") or "").strip()
        self.limit = max(1, min(3, int(config.get("pagination_limit", 1)), max_pages)) if self.selector else 1
        self.item_limit = max(1, items_per_section) * self.limit
        self.items, self.seen_items, self.seen_pages = [], set(), set()
        self.report = {"start_url": start_url, "page_limit": self.limit, "item_limit": self.item_limit,
                       "pages": [], "stop_reason": None, "truncated_items": 0}

    def within_column(self, url):
        try:
            start, target = urlsplit(self.start_url), urlsplit(url)
            if target.scheme not in {"http", "https"} or target.username or target.password or _origin(start) != _origin(target):
                return False
            path = posixpath.normpath(unquote(target.path))
            initial = posixpath.normpath(unquote(start.path))
            stem = str(PurePosixPath(initial).with_suffix("")) if PurePosixPath(initial).suffix.lower() in {".htm", ".html", ".shtml"} else initial
            wordpress_page = not PurePosixPath(initial).suffix and bool(re.fullmatch(re.escape(initial.rstrip("/")) + r"/page/[1-9]\d*", path))
            if path != initial and not (stem != initial and path.startswith(stem + "/")) and not wordpress_page:
                return False
            stable = lambda parsed: sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if v and k.casefold() not in PAGE_PARAMS)
            return stable(start) == stable(target)
        except ValueError:
            return False

    def consume(self, html, page_url, parsed):
        """Append one observed page and return its allowed, unvisited next link."""
        if self.report["pages"] and not self.within_column(page_url):
            self.report["stop_reason"] = "REDIRECT_OUTSIDE_COLUMN"
            raise ValueError("PAGINATION_REDIRECT_OUTSIDE_COLUMN")
        key = _page_key(page_url)
        if key in self.seen_pages:
            self.report["stop_reason"] = "PAGE_CYCLE"
            return None
        self.seen_pages.add(key)
        added = 0
        for item in parsed:
            identity = canonicalize_url(item.url)
            if identity in self.seen_items:
                continue
            self.seen_items.add(identity)
            if len(self.items) < self.item_limit:
                self.items.append(item)
                added += 1
            else:
                self.report["truncated_items"] += 1
        self.report["pages"].append({"url": page_url, "parsed_items": len(parsed), "added_items": added})
        if not added and len(self.report["pages"]) > 1:
            self.report["stop_reason"] = "REPEATED_PAGE" if parsed else "EMPTY_PAGE"
            return None
        if len(self.items) >= self.item_limit:
            self.report["stop_reason"] = "ITEM_LIMIT"
            return None
        if len(self.report["pages"]) >= self.limit:
            self.report["stop_reason"] = "PAGE_LIMIT"
            return None
        if not self.selector:
            self.report["stop_reason"] = "NO_NEXT_SELECTOR"
            return None
        try:
            soup = BeautifulSoup(html, "html.parser")
            node = soup.select_one(self.selector)
        except Exception as exc:
            raise ValueError("The next-page selector is invalid") from exc
        if not isinstance(node, Tag):
            self.report["stop_reason"] = "NO_NEXT_PAGE"
            return None
        for parent in (node, *node.parents):
            if not isinstance(parent, Tag):
                continue
            if parent.has_attr("disabled") or str(parent.get("aria-disabled", "")).casefold() == "true" or "disabled" in parent.get("class", []):
                self.report["stop_reason"] = "DISABLED_NEXT_PAGE"
                return None
        href = str(node.get("href") or "").strip()
        if not href:
            self.report["stop_reason"] = "NO_NEXT_PAGE"
            return None
        target = None
        if href.casefold() in {"javascript:", "javascript:;"}:
            target = _observed_get_form(soup, node, page_url)
            if target:
                self.report["pages"][-1]["next_link_kind"] = "OBSERVED_PUBLIC_GET_FORM"
        if target is None and (href.startswith("#") or re.search(r"[<>\x00-\x20]", href) or urlsplit(urljoin(page_url, href)).scheme not in {"http", "https"}):
            self.report["stop_reason"] = "INVALID_NEXT_LINK"
            return None
        target = target or urljoin(page_url, href)
        if not self.within_column(target):
            self.report["stop_reason"] = "NEXT_PAGE_OUTSIDE_COLUMN"
            return None
        if _page_key(target) in self.seen_pages:
            self.report["stop_reason"] = "PAGE_CYCLE"
            return None
        return target
