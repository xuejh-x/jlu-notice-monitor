"""Read-only, resumable JLU directory discovery and parser compatibility audit.

Never imports the crawler, API, models or database. Production configuration is
read only. Public HTML and sanitized request evidence stay in docs/.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EVIDENCE = ROOT / "docs/jlu-audit-evidence"
OUTPUT_DOCS = ROOT / "docs"
# Set before importing application modules, even though this script uses no DB.
os.environ["JLU_DATABASE_URL"] = "sqlite://"
os.environ["JLU_APP_DATA_DIR"] = str(EVIDENCE / "runtime")
os.environ["JLU_SCHEDULER_ENABLED"] = "false"
os.environ["JLU_STARTUP_SYNC_ENABLED"] = "false"
sys.path.insert(0, str(ROOT / "backend"))

import httpx
import certifi
from bs4 import BeautifulSoup
from app.config import load_yaml
from app.parsers import parse_list_html, parse_detail_html
from app.parsers.html import CONTENT_SELECTORS, HTMLParseError
from app.services.source_identity import canonicalize_source_url
from app.services.dates import parse_date
from app.services.normalization import normalize_title
from app.services.attachment_validation import classify_attachment_prefix
from app.sources.generic import SafeFetcher, GenericPublicSource
from app.sources.registry import build_source
from app.sources.oa_public import parse_oa_attachment_references

UA = "JLUNoticeMonitor-Audit/0.1"
DIRECTORIES = {
    "管理服务": "https://www.jlu.edu.cn/jgsz/gl_fwyywjg.htm",
    "院系": "https://www.jlu.edu.cn/jgsz/yxsz.htm",
    "研究机构": "https://www.jlu.edu.cn/jgsz/yjjg.htm",
    "附属单位": "https://www.jlu.edu.cn/jgsz/fsdwjxgqy.htm",
}
NOTICE = re.compile(r"通知|公告|公示|教学信息|就业信息|人才招聘|招聘信息|招聘公告|竞赛信息|竞赛通知|招生信息|招标信息")
HUB = re.compile(r"^(本科生教育|本科教学|本科生教学|研究生教育|研究生教学|人才培养|学生工作|学生天地|招生就业|就业指导|教育教学|教学工作|创新创业|科学研究|科研工作|学生管理|通知公告|信息公开)$")
AUTH = re.compile(r"统一身份认证|统一身份验证|用户登录|身份认证平台|登录统一认证|请输入验证码|安全验证")


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def norm(url):
    # Source identity's canonicalizer escapes some legal path punctuation. Keep
    # the original routing characters for Struts (!)/GSAPP (*) requests.
    return canonicalize_source_url(url).replace("%21", "!").replace("%2A", "*")


def request_url(url):
    # Identity canonicalization can remove a meaningful trailing slash, query
    # order or tracking-looking parameter. Never use it as an HTTP target/key.
    return urlunsplit(urlsplit(url.strip())._replace(fragment=""))


def text(node):
    return " ".join(node.get_text(" ", strip=True).split())


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(6):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.15 * (attempt + 1))


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class AuditFetch:
    """Existing TLS/URL security with serial throttling, robots and disk cache."""
    def __init__(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "html").mkdir(exist_ok=True)
        self.cache = load_json(EVIDENCE / "requests.json", {})
        self.robots = {}
        self.last = 0.0
        self.host_last = {}
        self.request_count = 0
        self.fetcher = SafeFetcher(validation_scope="local", allow_private_network=False)
        self.fetcher.retries = 0  # retry transient failures only, at most once
        self.fetcher.client.timeout = httpx.Timeout(12)
        self.fetcher.client.headers["User-Agent"] = UA
        self.fetcher.client.event_hooks = {"request": [self.before], "response": [self.after]}
        self.responses = []

    async def before(self, request):
        url = str(request.url)
        origin = urlunsplit((*urlsplit(url)[:2], "", "", ""))
        if urlsplit(url).path != "/robots.txt":
            await self.check_robots(url)
        robot = self.robots.get(origin)
        delay = max(1.2, float(robot.crawl_delay(UA) or 0)) if robot else 1.2
        wait = max(self.last + 1.0, self.host_last.get(origin, 0) + delay) - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self.last = time.monotonic()
        self.host_last[origin] = self.last
        self.request_count += 1

    async def after(self, response):
        record = {"url": str(response.url), "time": now(), "status": response.status_code,
                  "content_type": response.headers.get("content-type", ""),
                  "location": response.headers.get("location", "")}
        self.responses.append(record)
        with (EVIDENCE / "http.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if response.status_code in {401, 403, 429}:
            # No retry or authentication/captcha bypass.
            raise RuntimeError(f"ACCESS_RESTRICTED_HTTP_{response.status_code}: {response.url}")

    async def check_robots(self, url):
        p = urlsplit(url)
        origin = urlunsplit((p.scheme, p.netloc, "", "", ""))
        if origin not in self.robots:
            r = await self.get(origin + "/robots.txt", robot=True)
            rp = RobotFileParser(origin + "/robots.txt")
            if r.get("status") in {404, 410}:
                rp.parse([])
            elif r.get("ok") and not r.get("auth"):
                rp.parse(r["html"].splitlines())
            else:
                raise RuntimeError("ROBOTS_UNAVAILABLE: " + r.get("error", str(r.get("status"))))
            self.robots[origin] = rp
        if not self.robots[origin].can_fetch(UA, url):
            raise RuntimeError("ROBOTS_DISALLOWED: " + url)

    async def get(self, url, robot=False, attempt_budget=2):
        url = request_url(url)
        cached = self.cache.get(url)
        if cached:
            return self.inflate(cached)
        record = {"url": url, "time": now(), "ok": False}
        for attempt in range(attempt_budget):
            start = len(self.responses)
            try:
                html, ct, final = await self.fetcher.get(url)
                record.update(ok=True, final_url=final, content_type=ct, status=200,
                              auth=bool(AUTH.search(html[:50000])) and bool(BeautifulSoup(html, "html.parser").select("input[type=password], form[action*=login]")))
                digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
                record.update(sha256=digest, html_path=f"html/{digest}.html",
                              replacement_chars=html.count("\ufffd"), chars=len(html))
                (EVIDENCE / record["html_path"]).write_bytes(html.encode("utf-8"))
                break
            except Exception as exc:
                causes = []
                current_error = exc
                while current_error is not None and len(causes) < 8:
                    causes.append(f"{type(current_error).__name__}: {str(current_error) or repr(current_error)}")
                    current_error = current_error.__cause__ or current_error.__context__
                record["error"] = " <- ".join(causes)
                responses = [x for x in self.responses[start:] if robot or urlsplit(x["url"]).path != "/robots.txt"]
                if responses:
                    record["status"] = responses[-1]["status"]
                if attempt + 1 < attempt_budget and ("Timeout" in record["error"] or record.get("status") in {502, 503, 504}):
                    await asyncio.sleep(2)
                    continue
                break
        record["attempts"] = attempt + 1
        self.cache[url] = record
        save_json(EVIDENCE / "requests.json", self.cache)
        return self.inflate(record)

    @staticmethod
    def inflate(record):
        value = dict(record)
        if record.get("html_path"):
            value["html"] = (EVIDENCE / record["html_path"]).read_bytes().decode("utf-8")
        return value

    async def close(self):
        await self.fetcher.close()

    async def attachment(self, url):
        """Read <=1 KiB with Range; never downloads a whole attachment."""
        key = "attachment:" + norm(url)
        if key in self.cache:
            return self.cache[key]
        r = {"url": url, "time": now(), "ok": False, "method": "GET Range bytes=0-1023"}
        current = url
        try:
            for _ in range(4):
                await self.fetcher.validate_url(current)
                async with self.fetcher.client.stream("GET", current, headers={"Range": "bytes=0-1023"}) as response:
                    r.update(status=response.status_code, final_url=str(response.url),
                             content_type=response.headers.get("content-type", ""),
                             disposition=response.headers.get("content-disposition", ""))
                    if response.is_redirect:
                        current = urljoin(current, response.headers.get("location", ""))
                        continue
                    response.raise_for_status()
                    head = b""
                    async for chunk in response.aiter_bytes(chunk_size=1024):
                        head = chunk[:1024]
                        break
                    r["prefix_hex"] = head[:16].hex()
                    r["read_bytes"] = len(head)
                    r["classification"] = classify_attachment_prefix(response.status_code, response.headers, head)
                    r["ok"] = r["classification"]["file_prefix_verified"]
                    if not r["ok"]:
                        r["error"] = r["classification"]["category"] + ": " + r["classification"]["reason"]
                    break
            else:
                r["error"] = "REDIRECT_LIMIT"
        except Exception as exc:
            r["error"] = f"{type(exc).__name__}: {exc}"
        self.cache[key] = r
        save_json(EVIDENCE / "requests.json", self.cache)
        return r


async def directories(fetch):
    for category, url in DIRECTORIES.items():
        r = await fetch.get(url)
        if not r["ok"]:
            print(category, r, flush=True)
            continue
        soup = BeautifulSoup(r["html"], "html.parser")
        nodes = [(s, len(soup.select(s))) for s in [".v_news_content", "#vsb_content", ".content", "table"]]
        print(category, nodes, flush=True)
        content = soup.select_one(".v_news_content, #vsb_content") or soup
        print(str(content)[:2400], flush=True)


def priority(name, category, configured=False):
    if configured or name in {"吉林大学", "吉林大学 OA 校内通知"}:
        return "P0"
    if re.search("本科生院|研究生院|学生工作|学生就业|科学技术|科研院|科技管理|社会科学|创新创业|教务|招生|团委", name):
        return "P1"
    return "P2" if category == "院系" or "学院" in name else "P3"


def column_links(html, base):
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.select("a[href]"):
        label = text(a) or str(a.get("title") or "") or " ".join(str(i.get("alt") or "") for i in a.select("img"))
        if not NOTICE.search(label) and re.search(r"more|更多|查看|^>>|^\+", label, re.I):
            parent = a.parent
            for _ in range(2):
                if parent is None:
                    break
                parent_text = text(parent)
                if NOTICE.search(parent_text) and len(parent_text) <= 80:
                    title_node = parent.select_one("h2, h3, h4, .title, .tit")
                    label = text(title_node) if title_node else parent_text
                    label = re.sub(r"more.*|查看更多.*|更多.*", "", label, flags=re.I).strip()
                    break
                parent = parent.parent
        href = str(a.get("href", "")).strip()
        if not (2 <= len(label) <= 28 and NOTICE.search(label)):
            continue
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        url = urljoin(base, href)
        p = urlsplit(url)
        if p.scheme not in {"http", "https"} or re.search(r"/info/|getInformation\.action|/(?:wujia_detail_g7yU_\d+|tongzhiy/detail_g7yU_\d+)/\d+\.html$|\.(pdf|docx?|xlsx?|zip)$", p.path, re.I):
            continue
        if re.search(r"(?:^|[?&])(id|articleId)=", p.query, re.I) or "urltype=news.NewsContentUrl" in p.query:
            continue
        found[norm(url)] = label
    return found


async def discover(fetch):
    units = []
    sites = {}
    def add_unit(name, site, category, evidence, basis):
        name = re.sub(r"^\d+[.、]\s*", "", name).strip()
        if len(name) < 2:
            return
        site = norm(site) if site else ""
        unit = dict(institution=name, category=category, site_url=site, discovery_url=evidence,
                    discovery_basis=basis, discovered_at=now(), priority=priority(name, category))
        units.append(unit)
        if site:
            item = sites.setdefault(site, dict(site_url=site, institutions=[], categories=[], discovery_urls=[]))
            for key, value in [("institutions", name), ("categories", category), ("discovery_urls", evidence)]:
                if value not in item[key]:
                    item[key].append(value)

    for category, url in DIRECTORIES.items():
        r = await fetch.get(url)
        if not r["ok"]:
            raise RuntimeError(f"Official directory unavailable: {url}")
        soup = BeautifulSoup(r["html"], "html.parser")
        content = soup.select_one("#vsb_content")
        if not content:
            raise RuntimeError(f"Directory markup changed: {url}")
        for a in content.select("a[href]"):
            href = urljoin(url, str(a["href"]))
            if urlsplit(href).scheme in {"http", "https"}:
                add_unit(text(a), href, category, url, "官方机构目录直接链接")
        # Retain every unlinked table cell and unlinked administrative paragraph.
        for node in content.select("td" if category != "管理服务" else "p"):
            if node.select("a[href]") or node.get("colspan") or node.find("td"):
                continue
            label = text(node)
            if not label or len(label) > 100 or re.match(r"^[（(]?[一二三四五六七八九十]+[、）)]", label):
                continue
            if label in {"吉林大学机构设置", "附属学校", "校管企业"}:
                continue
            add_unit(label, "", category, url, "官方目录列名但未提供独立官网链接；不推测域名")
        if category == "管理服务":
            for paragraph in content.select("p"):
                if not paragraph.select("a[href]"):
                    continue
                remaining = BeautifulSoup(str(paragraph), "html.parser")
                for a in remaining.select("a"):
                    a.decompose()
                label = re.sub(r"^\d+[.、]\s*", "", text(remaining)).strip(" 、，()（）")
                if label and len(label) < 80:
                    add_unit(label, "", category, url, "同段已链接机构旁的未链接名称；独立官网待确认")

    home = await fetch.get("https://www.jlu.edu.cn/")
    add_unit("吉林大学", "https://www.jlu.edu.cn/", "校级", "https://www.jlu.edu.cn/", "学校官方主页")
    if home["ok"]:
        soup = BeautifulSoup(home["html"], "html.parser")
        for a in soup.select("a[href]"):
            href = urljoin(home["final_url"], str(a["href"]))
            if urlsplit(href).scheme in {"http", "https"} and (urlsplit(href).hostname or "").endswith(".jlu.edu.cn") and not re.search(r"/info/", urlsplit(href).path):
                if re.search("教育|招生|就业|合作|通知|科研|图书|网络", text(a)) and len(text(a)) <= 30:
                    add_unit(text(a), href, "官网导航", home["final_url"], "学校官网导航明确链接")

    configs = load_yaml("sources.yaml")["sources"]
    columns = {}
    for config in configs:
        if not (urlsplit(config["base_url"]).hostname or "").endswith("jlu.edu.cn"):
            continue
        add_unit(config["name"], config["base_url"], "现有来源", "backend/config/sources.yaml", "现有来源回归清单")
        for section in config.get("sections", []):
            u = norm(section["url"])
            columns[u] = dict(column_url=u, column=section["name"], institution=config["name"],
                              site_url=norm(config["base_url"]), category="现有来源", priority="P0",
                              discovery_url="backend/config/sources.yaml", discovery_basis="现有正式配置",
                              configured_source=config["code"], discovered_at=now())
    for extra in load_json(EVIDENCE / "supplemental-seeds.json", []):
        add_unit(extra["institution"], extra["site_url"], extra["category"], extra["discovery_url"], extra["discovery_basis"])
        for c in extra.get("columns", []):
            u = norm(c["url"])
            columns.setdefault(u, dict(column_url=u, column=c["name"], institution=extra["institution"],
                                      site_url=norm(extra["site_url"]), category=extra["category"],
                                      priority=extra.get("priority", "P3"), discovery_url=extra["discovery_url"],
                                      discovery_basis=extra["discovery_basis"], configured_source="", discovered_at=now()))
    # Freeze complete directory-level seeds before fetching institutional sites.
    save_json(EVIDENCE / "units.json", units)
    save_json(EVIDENCE / "sites.json", list(sites.values()))
    old = {s["site_url"]: s for s in load_json(EVIDENCE / "discovery.json", [])}
    results = []
    for index, site in enumerate(sites.values(), 1):
        url = site["site_url"]
        print(f"DISCOVER {index}/{len(sites)} {url}", flush=True)
        retry_https = urlsplit(url).scheme == "http" and old.get(url, {}).get("status") == "unreachable" and "alternate_url" not in old.get(url, {})
        retry_recovered = old.get(url, {}).get("status") == "unreachable" and fetch.cache.get(norm(old.get(url, {}).get("alternate_url") or url), {}).get("ok")
        if url in old and not retry_https and not retry_recovered:
            result = old[url]
            for c in result.get("columns", []):
                columns.setdefault(c["column_url"], c)
            cached_pages = [url] + [h["url"] for h in result.get("hub_pages", [])]
            for page in cached_pages:
                cached = fetch.cache.get(norm(page), {})
                if not cached.get("ok") or cached.get("auth"):
                    continue
                value = fetch.inflate(cached)
                for link, label in column_links(value["html"], value["final_url"]).items():
                    c = dict(column_url=link, column=label, institution=" / ".join(site["institutions"]),
                             site_url=url, category=" / ".join(site["categories"]),
                             priority=min(priority(n, cat) for n in site["institutions"] for cat in site["categories"]),
                             discovery_url=page, discovery_basis="缓存官网页面的通知标题/更多链接补充识别", configured_source="", discovered_at=cached["time"])
                    if link not in columns:
                        columns[link] = c
                        result.setdefault("columns", []).append(c)
            if result.get("columns") and result.get("status") == "no_column_discovered":
                result.update(status="reachable", reason="通过通知标题旁更多链接补充发现栏目")
            results.append(result)
            continue
        r = await fetch.get(url)
        initial_error = ""
        alternate_url = ""
        if not r["ok"] and urlsplit(url).scheme == "http":
            initial_error = r.get("error", "")
            alternate_url = "https:" + url[len("http:"):]
            r = await fetch.get(alternate_url)
        result = dict(site, checked_at=r["time"], status="reachable" if r["ok"] else "unreachable",
                      reason=r.get("error", ""), final_url=r.get("final_url", ""), columns=[], hub_pages=[])
        if alternate_url:
            result.update(alternate_url=alternate_url, initial_http_error=initial_error)
        if r.get("auth"):
            result.update(status="authentication_required", reason="公开 URL 返回登录表单")
        elif r["ok"]:
            pages = [(r["html"], r["final_url"])]
            soup = BeautifulSoup(r["html"], "html.parser")
            hubs = []
            for a in soup.select("a[href]"):
                href = urljoin(r["final_url"], str(a["href"]))
                if HUB.match(text(a)) and urlsplit(href).scheme in {"http", "https"} and urlsplit(href).hostname == urlsplit(r["final_url"]).hostname:
                    if norm(href) != norm(r["final_url"]) and norm(href) not in hubs:
                        hubs.append(norm(href))
            for hub in hubs[:6]:
                h = await fetch.get(hub)
                result["hub_pages"].append({"url": hub, "ok": h["ok"], "reason": h.get("error", "")})
                if h["ok"] and not h.get("auth"):
                    pages.append((h["html"], h["final_url"]))
            result["hub_limit_omitted"] = hubs[6:]
            for html, page in pages:
                for link, label in column_links(html, page).items():
                    c = dict(column_url=link, column=label, institution=" / ".join(site["institutions"]),
                             site_url=url, category=" / ".join(site["categories"]),
                             priority=min(priority(n, cat) for n in site["institutions"] for cat in site["categories"]),
                             discovery_url=page, discovery_basis="官网首页或一级教学/学生/科研入口的栏目链接",
                             configured_source="", discovered_at=r["time"])
                    columns.setdefault(link, c)
                    result["columns"].append(c)
            if not result["columns"]:
                result.update(status="no_column_discovered", reason="首页和至多六个一级相关入口未发现通知栏目；不等于站点无通知")
        results.append(result)
        save_json(EVIDENCE / "discovery.json", results)
        save_json(EVIDENCE / "columns.json", list(columns.values()))
    save_json(EVIDENCE / "columns.json", list(columns.values()))
    save_json(EVIDENCE / "discovery.json", results)
    print(json.dumps({"units": len(units), "sites": len(sites), "columns": len(columns),
                      "site_states": dict(Counter(x["status"] for x in results))}, ensure_ascii=False), flush=True)


def error_category(r):
    message = r.get("error", "")
    if r.get("auth") or r.get("status") == 401:
        return "AUTH_REQUIRED"
    if "ROBOTS_DISALLOWED" in message:
        return "ROBOTS_DISALLOWED"
    if "ROBOTS_UNAVAILABLE" in message:
        return "ROBOTS_UNAVAILABLE"
    if "CERTIFICATE_VERIFY_FAILED" in message:
        return "TLS_CERTIFICATE_VERIFY_FAILED"
    if r.get("status") in {403, 429}:
        return "ACCESS_RESTRICTED"
    if r.get("status", 0) >= 400:
        return "HTTP_ERROR"
    if "Timeout" in message:
        return "TIMEOUT"
    if "UnsafeSourceUrl" in message:
        return "URL_SECURITY_REJECTED"
    return "NETWORK_ERROR"


def page_next(html, base):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.select("a[href]"):
        label = text(a).replace(" ", "")
        if label in {"下页", "下一页", "Next", "next", ">", "»"} or "next" in str(a.get("rel", "")):
            href = urljoin(base, str(a["href"]))
            if urlsplit(href).scheme in {"http", "https"} and norm(href) != norm(base):
                links.append(href)
    return list(dict.fromkeys(links))


def reference_articles(html, base):
    """Independent broad DOM inventory; candidate recall is a warning, not truth."""
    soup = BeautifulSoup(html, "html.parser")
    links = {}
    for a in soup.select("a[href]"):
        href = urljoin(base, str(a["href"]))
        if re.search(r"/info/[^/]+/[^/]+\.html?(?:[?#]|$)|getInformation\.action", href, re.I):
            label = str(a.get("title") or text(a)).strip()
            if label and not a.find_parent(["nav", "header", "footer"]):
                links[norm(href)] = label
    return links


def compact_title(value):
    return re.sub(r"\s+|\[置顶\]|【置顶】", "", value)


def inspect_detail(html, final_url, item, parsed):
    soup = BeautifulSoup(html, "html.parser")
    issues = []
    document_title = text(soup.title) if soup.title else ""
    heading_texts = [text(h) for h in soup.select("h1, h2, .article-title, .title, .content_t, .tit") if len(text(h)) > 6]
    expected = compact_title(item.title)
    detail_title = compact_title(parsed.title)
    title_verified = bool(expected and (expected in compact_title(document_title) or any(expected in compact_title(h) for h in heading_texts)))
    if not title_verified:
        issues.append("TITLE_NOT_IN_DETAIL_HEADING")
    if detail_title != expected and not (detail_title in expected or expected in detail_title):
        issues.append("TITLE_MISMATCH")
    known = [(s, soup.select_one(s)) for s in CONTENT_SELECTORS]
    chosen = next(((s, n) for s, n in known if n and len(n.get_text(strip=True)) >= 20), None)
    if not chosen:
        issues.append("BODY_CONTAINER_FALLBACK")
    if len(parsed.content) < 40:
        issues.append("BODY_TOO_SHORT")
    if sum(word in parsed.content for word in ["学校概况", "机构设置", "师资队伍", "友情链接", "网站地图", "版权所有"]) >= 3:
        issues.append("BODY_NAVIGATION_CONTAMINATION")
    if "\ufffd" in parsed.title or parsed.content.count("\ufffd") > 2:
        issues.append("ENCODING_REPLACEMENT")
    raw_text = soup.get_text(" ", strip=True)
    meta_match = re.search(r"(?:发布日期|发布时间|发表时间|发布时间|日期|时间)[：:\s]*?(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}日?)", raw_text)
    reference_date = parse_date(meta_match.group(1)) if meta_match else None
    if reference_date and parsed.publish_date != reference_date:
        issues.append("DATE_MISMATCH")
    if not parsed.publish_date:
        issues.append("DATE_MISSING")
    if item.publish_date and parsed.publish_date and item.publish_date != parsed.publish_date:
        issues.append("LIST_DETAIL_DATE_DIFFERENCE")
    raw_files = []
    for a in soup.select("a[href]"):
        href = urljoin(final_url, str(a["href"]))
        if re.search(r"\.(pdf|docx?|xlsx?|zip|rar|7z|pptx?)(?:[?&#]|$|\s)", href + " " + text(a), re.I) or "download.jsp" in href:
            raw_files.append({"url": href, "filename": text(a)})
    parsed_urls = {norm(a.url) for a in parsed.attachments}
    missing = [a for a in raw_files if norm(a["url"]) not in parsed_urls]
    if missing:
        issues.append("ATTACHMENT_MISSING")
    oa_refs = parse_oa_attachment_references(html, final_url)
    if oa_refs:
        issues.append("OA_ATTACHMENT_POST_NOT_EXERCISED")
    return dict(url=final_url, list_title=item.title, parsed_title=parsed.title,
                document_title=document_title, heading_texts=heading_texts[:6],
                title_verified=title_verified, list_date=str(item.publish_date or ""),
                parsed_date=str(parsed.publish_date or ""), reference_date=str(reference_date or ""),
                body_selector=chosen[0] if chosen else "body fallback or specialized OA",
                content_chars=len(parsed.content), content_preview=parsed.content[:400],
                content_sha256=hashlib.sha256(parsed.content.encode("utf-8")).hexdigest(),
                raw_attachments=raw_files, missing_attachments=missing,
                parsed_attachments=[a.model_dump() for a in parsed.attachments],
                oa_attachment_references=[dict(stored_name=a.stored_name, display_name=a.display_name) for a in oa_refs],
                issues=issues)


async def validate_one(fetch, column):
    url = column["column_url"]
    r = await fetch.get(url)
    result = dict(column, checked_at=r["time"], status="失败", issues=[], details=[],
                  list_count=0, list_items=[], generic_count=0, attachments_checked=0,
                  evidence_file="", reason="", pagination={})
    if not r["ok"] or r.get("auth"):
        issue = error_category(r)
        result.update(status="需认证" if issue == "AUTH_REQUIRED" else "失败", issues=[issue], reason=r.get("error", "登录表单"))
        return result
    html = r["html"]
    final = r["final_url"]
    result.update(final_url=final, list_sha256=r["sha256"], list_snapshot=r["html_path"], http_status=r["status"], content_type=r["content_type"])
    # Execute the same GenericPublicSource entry points as source preview, using
    # the audited read-only cache and request policy instead of its own network.
    generic = GenericPublicSource({"code": "audit", "name": "audit", "base_url": url, "parser": "auto"})
    original_fetcher = generic.fetcher
    class CachedFetcher:
        async def get(self, target):
            value = await fetch.get(target)
            if not value["ok"] or value.get("auth"):
                raise RuntimeError(value.get("error", "AUTH_REQUIRED"))
            return value["html"], value["content_type"], value["final_url"]
        async def validate_url(self, target):
            return await fetch.fetcher.validate_url(target)
    generic.fetcher = CachedFetcher()
    try:
        try:
            generic_items = await generic.fetch_list()
        except Exception as exc:
            generic_items = []
            result["generic_error"] = str(exc)
        result["generic_count"] = len(generic_items)
        adapter = None
        if column.get("configured_source"):
            config = next(c for c in load_yaml("sources.yaml")["sources"] if c["code"] == column["configured_source"])
            adapter = build_source(config)
            try:
                items = adapter.parse_list(html, final, column["column"])
            except HTMLParseError as exc:
                await adapter.close()
                result.update(status="失败", issues=["LIST_PARSE_REJECTED"], reason=str(exc))
                return result
            result["parser"] = config["parser"]
        else:
            items = generic_items
            result["parser"] = "auto"
        result["list_count"] = len(items)
        result["list_items"] = [i.model_dump(mode="json") for i in items]
        references = reference_articles(html, final)
        actual_urls = {norm(i.url) for i in items}
        result["reference_article_count"] = len(references)
        if urlsplit(final).path in {"", "/", "/index.htm", "/index.html"}:
            result["issues"].append("COLUMN_IS_HOMEPAGE_NEEDS_SCOPE_REVIEW")
        result["unparsed_reference_links"] = [{"url": k, "title": v} for k, v in references.items() if k not in actual_urls]
        if not items:
            result["issues"].append("EMPTY_LIST")
        elif len(result["unparsed_reference_links"]) > 0:
            result["issues"].append("LIST_CANDIDATE_RECALL_GAP")
        bad_links = [i.url for i in items if not re.search(r"/info/|getInformation\.action|/\d+\.html?|article|detail|content|show", i.url, re.I)]
        if bad_links:
            result["issues"].append("POSSIBLE_NAVIGATION_CAPTURE")
            result["suspicious_links"] = bad_links
        if items and not any(i.publish_date for i in items):
            result["issues"].append("LIST_DATES_MISSING")
        if r.get("replacement_chars", 0):
            result["issues"].append("ENCODING_REPLACEMENT")
        sample_count = 2 if column["priority"] in {"P0", "P1"} else 1
        for item in items[:sample_count]:
            d = await fetch.get(item.url)
            if not d["ok"] or d.get("auth"):
                result["details"].append(dict(url=item.url, time=d["time"], issues=[error_category(d)], error=d.get("error", "AUTH_REQUIRED")))
                result["issues"].append("DETAIL_" + error_category(d))
                continue
            try:
                if adapter:
                    # OA parse_detail method is generic; its specialized pure
                    # parser must be called explicitly, without attachment POST.
                    if result["parser"] == "oa_public":
                        from app.sources.oa_public import parse_oa_detail_html
                        parsed = parse_oa_detail_html(d["html"], d["final_url"], item)
                    else:
                        parsed = adapter.parse_detail(d["html"], item)
                else:
                    parsed = await generic.fetch_detail(item)
                detail = inspect_detail(d["html"], d["final_url"], item, parsed)
                if result["parser"] == "oa_public":
                    detail["issues"] = [i for i in detail["issues"] if i != "BODY_CONTAINER_FALLBACK"]
                detail.update(time=d["time"], sha256=d["sha256"], snapshot=d["html_path"], attachment_probes=[])
                # At most one file endpoint per sampled article.
                for attachment in parsed.attachments[:1]:
                    probe = await fetch.attachment(attachment.url)
                    detail["attachment_probes"].append(probe)
                    result["attachments_checked"] += 1
                    if not probe["ok"]:
                        detail["issues"].append("ATTACHMENT_ENDPOINT_FAILED")
                if len(parsed.attachments) > 1:
                    detail["issues"].append("ATTACHMENTS_UNCHECKED")
                result["details"].append(detail)
                result["issues"].extend(detail["issues"])
            except Exception as exc:
                result["details"].append(dict(url=item.url, time=d["time"], sha256=d["sha256"], snapshot=d["html_path"],
                                               error=str(exc), issues=["DETAIL_PARSE_ERROR"]))
                result["issues"].append("DETAIL_PARSE_ERROR")
        if adapter:
            await adapter.close()
        next_links = page_next(html, final)
        result["pagination"] = {"next_links": next_links, "production_follows_next": False, "checked": False}
        if next_links:
            p = await fetch.get(next_links[0])
            result["pagination"].update(checked=True, url=next_links[0], time=p["time"], ok=p["ok"], reason=p.get("error", ""))
            if p["ok"]:
                next_items = parse_list_html(p["html"], p["final_url"])
                result["pagination"].update(list_count=len(next_items), new_urls=len({norm(i.url) for i in next_items} - actual_urls), snapshot=p["html_path"])
                if not next_items:
                    result["issues"].append("PAGINATION_PARSE_EMPTY")
            else:
                result["issues"].append("PAGINATION_FETCH_FAILED")
            result["issues"].append("PAGINATION_NOT_CONFIGURED")
        elif re.search(r"共\s*\d+\s*页|下[一]?页|_totalpage|totalPage|totalPages", html, re.I):
            result["issues"].append("PAGINATION_DYNAMIC_OR_UNRESOLVED")
        result["issues"] = list(dict.fromkeys(result["issues"]))
        severe = {"EMPTY_LIST", "POSSIBLE_NAVIGATION_CAPTURE", "DETAIL_PARSE_ERROR", "BODY_NAVIGATION_CONTAMINATION"}
        if not items or not result["details"] or severe.intersection(result["issues"]) or all(d.get("error") for d in result["details"]):
            result["status"] = "失败"
        elif result["issues"]:
            result["status"] = "部分通过"
        else:
            result["status"] = "完全通过"
        result["reason"] = "; ".join(result["issues"]) or "样本标题、日期、正文、可见附件及分页检查无发现；仅代表本次样本"
        return result
    finally:
        await original_fetcher.close()


async def validate(fetch):
    columns = load_json(EVIDENCE / "columns.json", [])
    if not columns:
        raise RuntimeError("Complete discovery first")
    source_files = ["backend/config/sources.yaml", "backend/config/settings.yaml", "backend/app/sources/base.py",
                    "backend/app/sources/generic.py", "backend/app/sources/oa_public.py", "backend/app/parsers/html.py",
                    "backend/app/services/tls.py", "backend/app/services/source_security.py", "backend/app/crawler/runner.py"]
    source_files.extend(["backend/app/services/attachment_validation.py", "backend/scripts/audit_jlu_sites.py"])
    fingerprint = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files}
    previous = load_json(EVIDENCE / "validation-code-manifest.json", {})
    if (EVIDENCE / "results.json").exists() and previous.get("files") != fingerprint:
        raise RuntimeError("Parser fingerprint changed; use a new --output-dir instead of mixing cached verdicts")
    save_json(EVIDENCE / "validation-code-manifest.json", {"time": now(), "files": fingerprint,
              "python": sys.version, "database": "sqlite://", "deployment_tested": "local anonymous parser audit only"})
    columns.sort(key=lambda c: (c["priority"], c["site_url"], c["column_url"]))
    old = {r["column_url"]: r for r in load_json(EVIDENCE / "results.json", [])}
    results = []
    for index, c in enumerate(columns, 1):
        url = c["column_url"]
        if url in old:
            results.append(old[url])
            continue
        print(f"VALIDATE {index}/{len(columns)} {c['priority']} {url}", flush=True)
        try:
            result = await validate_one(fetch, c)
        except Exception as exc:
            result = dict(c, status="未检测", checked_at=now(), issues=["AUDIT_TOOL_ERROR"], reason=f"{type(exc).__name__}: {exc}")
        result["evidence_file"] = (EVIDENCE.relative_to(ROOT) / "results" / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")).as_posix()
        save_json(ROOT / result["evidence_file"], result)
        results.append(result)
        save_json(EVIDENCE / "results.json", results)
        print(f"  {result['status']} {result.get('list_count', 0)} {result['reason']}", flush=True)
    export()


async def tls_check(fetch):
    """Diagnostic certifi probe on six configured origins, not a Cloud run."""
    from app.services.source_security import validate_cloud_source_url
    origins = {}
    for c in load_yaml("sources.yaml")["sources"]:
        if (urlsplit(c["base_url"]).hostname or "").endswith("jlu.edu.cn"):
            origins[c["code"]] = c.get("sections", [{"url": c["base_url"]}])[0]["url"]
    existing = load_json(EVIDENCE / "tls-certifi.json", [])
    completed = {r["source"] for r in existing}
    await fetch.fetcher.close()
    fetch.fetcher.client = httpx.AsyncClient(verify=ssl.create_default_context(cafile=certifi.where()),
        trust_env=True, timeout=12, follow_redirects=False, headers={"User-Agent": UA},
        event_hooks={"request": [fetch.before], "response": [fetch.after]})
    for source, url in origins.items():
        if source in completed:
            continue
        result = dict(source=source, url=url, time=now(), scope="本机 certifi-only TLS 对照；非实际 Cloud", ok=False)
        try:
            await validate_cloud_source_url(url)
            result["cloud_dns_policy"] = "allowed"
        except Exception as exc:
            result["cloud_dns_policy"] = f"{type(exc).__name__}: {exc}"
        try:
            # get() has no new network on the main page cache; explicitly invoke
            # the existing fetcher for this independent TLS context instead.
            await fetch.check_robots(url)
            html, ct, final = await fetch.fetcher.get(url)
            result.update(ok=True, final_url=final, chars=len(html), content_type=ct)
        except Exception as exc:
            causes = []
            while exc is not None and len(causes) < 8:
                causes.append(f"{type(exc).__name__}: {exc}")
                exc = exc.__cause__ or exc.__context__
            result["error"] = " <- ".join(causes)
        existing.append(result)
        save_json(EVIDENCE / "tls-certifi.json", existing)
        print(json.dumps(result, ensure_ascii=False), flush=True)


async def recheck(fetch):
    """One extra attempt only for transient records that have just one attempt."""
    failed = [(u, r) for u, r in fetch.cache.items() if not r.get("ok") and not u.startswith("attachment:")
              and r.get("attempts", 1) < 2 and r.get("status") not in {401, 403, 404, 410, 429}
              and not any(s in r.get("error", "") for s in ["CERTIFICATE_VERIFY_FAILED", "ROBOTS_DISALLOWED", "redirect limit"])]
    failed.sort(key=lambda pair: (urlsplit(pair[0]).path != "/robots.txt", pair[0]))
    history = load_json(EVIDENCE / "retry-history.json", [])
    for url, previous in failed:
        fetch.cache.pop(url, None)
        value = await fetch.get(url, robot=urlsplit(url).path == "/robots.txt", attempt_budget=1)
        value["attempts"] = previous.get("attempts", 1) + 1
        fetch.cache[norm(url)]["attempts"] = value["attempts"]
        history.append(dict(previous=previous, rechecked={k: v for k, v in value.items() if k != "html"}))
        save_json(EVIDENCE / "retry-history.json", history)
        save_json(EVIDENCE / "requests.json", fetch.cache)
        print(f"RECHECK {url} {'recovered' if value['ok'] else value.get('error')}", flush=True)
    # Only retry a parser result if one of its failed response gates recovered.
    results = load_json(EVIDENCE / "results.json", [])
    retained = []
    removed = []
    for r in results:
        affected = [r["column_url"]] + [d["url"] for d in r.get("details", []) if d.get("error")]
        recovered = any(fetch.cache.get(norm(u), {}).get("ok") and any(h["previous"]["url"] == norm(u) for h in history) for u in affected)
        if recovered and r.get("status") != "完全通过":
            removed.append(r)
        else:
            retained.append(r)
    if removed:
        save_json(EVIDENCE / "pre-recheck-results.json", removed)
        save_json(EVIDENCE / "results.json", retained)
    print(f"Reopened {len(removed)} result rows after recovered transport gates", flush=True)


def self_check():
    fixture = ROOT / "backend/tests/fixtures"
    listing = (fixture / "list.html").read_text(encoding="utf-8")
    detail = (fixture / "detail.html").read_text(encoding="utf-8")
    items = parse_list_html(listing, "https://ccst.jlu.edu.cn/list.htm")
    parsed = parse_detail_html(detail, items[0].url, items[0])
    good = inspect_detail(detail, parsed.url, items[0], parsed)
    assert "TITLE_MISMATCH" not in good["issues"]
    wrong_title = parsed.model_copy(update={"title": "学校概况"})
    assert "TITLE_MISMATCH" in inspect_detail(detail, parsed.url, items[0], wrong_title)["issues"]
    missing_attachment = parsed.model_copy(update={"attachments": []})
    assert "ATTACHMENT_MISSING" in inspect_detail(detail, parsed.url, items[0], missing_attachment)["issues"]
    nav = '<html><title>网站导航</title><body>学校概况 机构设置 师资队伍 友情链接 版权所有</body></html>'
    # Inspection still diagnoses historical fallback output; the B1 parser
    # itself must now reject this page before producing a candidate.
    try:
        parse_detail_html(nav, items[0].url, items[0])
    except HTMLParseError:
        pass
    else:
        raise AssertionError("Navigation-only body must be rejected")
    bad = items[0].model_copy(update={"content": "学校概况 机构设置 师资队伍 友情链接 版权所有"})
    findings = inspect_detail(nav, items[0].url, items[0], bad)["issues"]
    assert {"BODY_CONTAINER_FALLBACK", "BODY_NAVIGATION_CONTAMINATION", "TITLE_NOT_IN_DETAIL_HEADING"} <= set(findings)
    assert column_links('<div><h2>通知公告</h2><a href="tzgg.htm">查看更多</a></div>', 'https://xsc.jlu.edu.cn/') == {'https://xsc.jlu.edu.cn/tzgg.htm': '通知公告'}
    assert page_next('<a href="tzgg/2.htm">下页</a>', 'https://example.org/tzgg.htm') == ['https://example.org/tzgg/2.htm']
    assert norm('https://OA.JLU.EDU.CN/defaultroot/PortalInformation!jldxList.action?channelId=179577#top') == 'https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577'
    save_json(EVIDENCE / "audit-self-check.json", {"time": now(), "checks": 7, "status": "passed", "network_requests": 0})
    print("7 offline audit safety/false-positive checks passed", flush=True)


def export():
    units = load_json(EVIDENCE / "units.json", [])
    # Supplementary official evidence can resolve a directory's unlinked unit;
    # do not keep calling it unknown after its exact name has a proven website.
    known_units = {u["institution"]: u for u in units if u.get("site_url")}
    for u in units:
        if not u.get("site_url") and u["institution"] in known_units:
            proven = known_units[u["institution"]]
            u["site_url"] = proven["site_url"]
            u["discovery_url"] += " | " + proven["discovery_url"]
            u["discovery_basis"] += "；后由同名机构的官方补充证据确认官网"
    sites = load_json(EVIDENCE / "sites.json", [])
    discovery = {s["site_url"]: s for s in load_json(EVIDENCE / "discovery.json", [])}
    columns = load_json(EVIDENCE / "columns.json", [])
    results = load_json(EVIDENCE / "results.json", [])
    by_url = {r["column_url"]: r for r in results}
    inventory = []
    for u in units:
        inventory.append(dict(u, record_type="institution", scope=u["category"],
                              state="linked_official_site" if u["site_url"] else "official_site_unknown",
                              reason="" if u["site_url"] else "目录未链接官网；未验证，不认定无需适配"))
    for s in sites:
        d = discovery.get(s["site_url"], {})
        inventory.append(dict(record_type="site", institution=" / ".join(s["institutions"]),
                              site_url=s["site_url"], category=" / ".join(s["categories"]),
                              scope="该机构公开网站；未登录", discovery_url=" | ".join(s["discovery_urls"]),
                              discovery_basis="官方目录/导航或已配置来源", state=d.get("status", "not_checked"),
                              reason=d.get("reason", ""), checked_at=d.get("checked_at", ""),
                              final_url=d.get("final_url", "")))
    for c in columns:
        r = by_url.get(c["column_url"], {})
        inventory.append(dict(c, record_type="column", scope="公开栏目首屏及有限详情样本；非历史全量",
                              state=r.get("status", "未检测"), reason=r.get("reason", "尚未执行适配检测"),
                              checked_at=r.get("checked_at", ""), final_url=r.get("final_url", "")))
    fields = ["record_type", "institution", "category", "site_url", "column", "column_url", "priority", "configured_source",
              "scope", "discovery_url", "discovery_basis", "discovered_at", "state", "checked_at", "final_url", "reason"]
    write_csv(OUTPUT_DOCS / "jlu-site-inventory.csv", inventory, fields)
    compatibility = []
    for c in columns:
        r = by_url.get(c["column_url"], {})
        compatibility.append(dict(c, checked_at=r.get("checked_at", ""), status=r.get("status", "未检测"),
                                  parser=r.get("parser", ""), http_status=r.get("http_status", ""),
                                  list_count=r.get("list_count", ""), generic_count=r.get("generic_count", ""),
                                  details_checked=len(r.get("details", [])), attachments_checked=r.get("attachments_checked", 0),
                                  pagination_checked=r.get("pagination", {}).get("checked", False),
                                  issues=" | ".join(r.get("issues", [])), reason=r.get("reason", "尚未检测"),
                                  evidence_file=r.get("evidence_file", ""), final_url=r.get("final_url", ""),
                                  verification_scope="本机公开匿名访问；Cloud 生产执行未验证",
                                  support_status="既有正式配置；本轮回归结果" if c.get("configured_source") else "未登记支持；仅审计结果"))
    write_csv(OUTPUT_DOCS / "jlu-compatibility-report.csv", compatibility,
              ["institution", "category", "site_url", "column", "column_url", "priority", "configured_source", "parser", "status", "checked_at",
               "http_status", "final_url", "list_count", "generic_count", "details_checked", "attachments_checked", "pagination_checked",
               "issues", "reason", "verification_scope", "support_status", "evidence_file", "discovery_url"])
    # Exact URL repetition is observed; title/date repetition is a candidate,
    # not an instruction to merge notices from different institutions.
    urls = defaultdict(list)
    titles = defaultdict(list)
    for r in results:
        if r.get("status") not in {"完全通过", "部分通过"} or "POSSIBLE_NAVIGATION_CAPTURE" in r.get("issues", []):
            continue
        for item in r.get("list_items", []):
            occurrence = dict(column_url=r["column_url"], url=item["url"], title=item["title"], date=item["publish_date"])
            urls[norm(item["url"])].append(occurrence)
            if item["publish_date"] and len(normalize_title(item["title"])) >= 8:
                titles[(normalize_title(item["title"]), item["publish_date"])].append(occurrence)
    repeated_urls = {u: v for u, v in urls.items() if len({x["column_url"] for x in v}) > 1}
    repeated_titles = [v for v in titles.values() if len({norm(x["url"]) for x in v}) > 1]
    save_json(EVIDENCE / "duplicates.json", dict(same_url_groups=repeated_urls, title_date_candidates=repeated_titles))
    summary = dict(generated_at=now(), institution_rows=len(units),
                   distinct_institution_labels=len({u["institution"] for u in units}),
                   units_without_site=sum(not u["site_url"] for u in units),
                   site_seed_urls=len(sites), distinct_seed_hosts=len({urlsplit(s["site_url"]).hostname for s in sites}),
                   site_discovery_completed=len(discovery),
                   distinct_final_site_urls=len({norm(d["final_url"]) for d in discovery.values() if d.get("final_url")}),
                   distinct_final_site_hosts=len({urlsplit(d["final_url"]).hostname for d in discovery.values() if d.get("final_url")}),
                   site_states=dict(Counter(d["status"] for d in discovery.values())),
                   distinct_columns=len(columns), columns_attempted=len(results),
                   columns_checked=sum(r["status"] in {"完全通过", "部分通过", "失败", "需认证"} for r in results),
                   columns_unchecked=len(columns) - sum(r["status"] in {"完全通过", "部分通过", "失败", "需认证", "无需适配"} for r in results),
                   no_adaptation_needed=sum(r["status"] == "无需适配" for r in results),
                   compatibility_states=dict(Counter(r["status"] for r in results)),
                   issue_counts=dict(Counter(i for r in results for i in r.get("issues", []))),
                   sampled_details=sum(len(r.get("details", [])) for r in results),
                   attachment_endpoints_checked=sum(r.get("attachments_checked", 0) for r in results),
                   pagination_pages_checked=sum(bool(r.get("pagination", {}).get("checked")) for r in results),
                   same_url_duplicate_groups=len(repeated_urls), title_date_duplicate_candidates=len(repeated_titles),
                   request_cache_entries=len(load_json(EVIDENCE / "requests.json", {})))
    save_json(EVIDENCE / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def review():
    """Conservative evidence review; all changes preserve original findings."""
    columns = load_json(EVIDENCE / "columns.json", [])
    results = load_json(EVIDENCE / "results.json", [])
    allowed_hosts = {urlsplit(s["site_url"]).hostname for s in load_json(EVIDENCE / "sites.json", [])}
    # Merge transport aliases only with observed same redirect target or exact
    # public HTML hash. Host/path/query equality alone is insufficient.
    observed = {norm(r["column_url"]): r for r in results}
    transport_aliases = {}
    for key, r in observed.items():
        p = urlsplit(key)
        if p.scheme != "http":
            continue
        secure = urlunsplit(("https", p.netloc, p.path, p.query, ""))
        other = observed.get(secure)
        if not other:
            continue
        same_final = r.get("final_url") and other.get("final_url") and norm(r["final_url"]) == norm(other["final_url"])
        same_html = r.get("list_sha256") and r.get("list_sha256") == other.get("list_sha256")
        if same_final or same_html:
            transport_aliases[key] = secure
    unique_columns = {}
    aliases = load_json(EVIDENCE / "url-aliases.json", [])
    columns.sort(key=lambda c: (urlsplit(c["column_url"]).scheme != "https", c["priority"]))
    for c in columns:
        normalized = norm(c["column_url"])
        key = transport_aliases.get(normalized, normalized)
        if key in unique_columns:
            aliases.append({"canonical": key, "alias": c["column_url"], "reason": "观察到相同最终URL/HTML哈希的HTTP与HTTPS别名" if normalized in transport_aliases else "同一 URL 的合法路径字符与百分号编码重复"})
            continue
        c["column_url"] = key
        if not c.get("configured_source"):
            c["priority"] = "P0" if "校级" in c.get("category", "") else priority(c.get("institution", ""), c.get("category", ""))
        unique_columns[key] = c
    unique_results = {}
    changes = load_json(EVIDENCE / "review-decisions.json", [])
    initial = {norm(r["column_url"]): r for r in load_json(EVIDENCE / "initial-validation-results.json", [])}
    results.sort(key=lambda r: (urlsplit(r["column_url"]).scheme != "https", r["priority"]))
    for r in results:
        normalized = norm(r["column_url"])
        key = transport_aliases.get(normalized, normalized)
        if key in unique_results:
            continue
        candidate_host = urlsplit(key).hostname or ""
        single_article = re.search(r"/\d{8,}\.html?$|/20\d{2}/\d{1,2}/\d+\.html?$", urlsplit(key).path) or "news.NewsContentUrl" in urlsplit(key).query
        if r.get("status") == "无需适配" and candidate_host.endswith(".jlu.edu.cn") and not single_article and key in initial:
            changes.append({"url": key, "time": now(), "reason": "修正范围判断：吉大域下官方页面即使不在目录种子主机表也必须保留，恢复原始访问检查证据", "original_status": "无需适配", "reviewed_status": initial[key]["status"]})
            r = json.loads(json.dumps(initial[key], ensure_ascii=False))
        original = json.loads(json.dumps(r, ensure_ascii=False))
        r["column_url"] = key
        r["priority"] = unique_columns[key]["priority"]
        issues = r.get("issues", [])
        host = urlsplit(key).hostname or ""
        single_article = re.search(r"/\d{8,}\.html?$|/20\d{2}/\d{1,2}/\d+\.html?$", urlsplit(key).path) or "news.NewsContentUrl" in urlsplit(key).query
        outside_domain = host not in allowed_hosts and host != "jlu.edu.cn" and not host.endswith(".jlu.edu.cn")
        if outside_domain or single_article:
            r.update(status="无需适配", reason="范围复核：外部全国平台引用或单篇文章链接，不是本专项的吉大通知栏目", issues=["OUT_OF_SCOPE_REFERENCE"])
        else:
            snapshot = r.get("list_snapshot")
            if snapshot and (EVIDENCE / snapshot).exists():
                html = (EVIDENCE / snapshot).read_text(encoding="utf-8")
                soup = BeautifulSoup(html, "html.parser")
                disabled_next = soup.select_one(".p_next_d")
                current_page = soup.select_one(".p_no_d")
                one_page = disabled_next and current_page and text(current_page) == "1" and not soup.select(".p_no a, .p_prev a, .p_next a")
                if one_page and "PAGINATION_DYNAMIC_OR_UNRESOLVED" in issues:
                    issues.remove("PAGINATION_DYNAMIC_OR_UNRESOLVED")
                    r.setdefault("pagination", {}).update(verified_single_page=True, review_basis="VSB 当前第1页，翻页按钮禁用且无其他页码链接")
            for d in r.get("details", []):
                if d.get("list_title", "").endswith(("...", "…")) and compact_title(d["list_title"].rstrip(".…")) in compact_title(d.get("document_title", "")):
                    if "TITLE_TRUNCATED" not in issues:
                        issues.append("TITLE_TRUNCATED")
                    if "TITLE_TRUNCATED" not in d.get("issues", []):
                        d.setdefault("issues", []).append("TITLE_TRUNCATED")
            r["issues"] = list(dict.fromkeys(issues))
            if r.get("list_count") and r.get("details") and not r["issues"]:
                r.update(status="完全通过", reason="本次样本标题、日期、正文、可见附件与单页状态检查无发现；非历史全量或Cloud认证")
            elif r["status"] in {"完全通过", "部分通过"}:
                r.update(status="部分通过", reason="; ".join(r["issues"]))
        if r != original:
            changes.append({"url": key, "time": now(), "original_status": original.get("status"),
                            "original_issues": original.get("issues", []), "reviewed_status": r.get("status"),
                            "reviewed_issues": r.get("issues", []), "reason": r.get("reason")})
        if r.get("evidence_file"):
            save_json(ROOT / r["evidence_file"], r)
        unique_results[key] = r
    unique_aliases = {(a["canonical"], a["alias"]): a for a in aliases}
    save_json(EVIDENCE / "url-aliases.json", list(unique_aliases.values()))
    save_json(EVIDENCE / "review-decisions.json", changes)
    save_json(EVIDENCE / "columns.json", list(unique_columns.values()))
    save_json(EVIDENCE / "results.json", list(unique_results.values()))
    export()


def report():
    summary = load_json(EVIDENCE / "summary.json", {})
    results = load_json(EVIDENCE / "results.json", [])
    discovery = load_json(EVIDENCE / "discovery.json", [])
    states = summary.get("compatibility_states", {})
    alias_count = len(load_json(EVIDENCE / "url-aliases.json", []))
    tests = (EVIDENCE / "backend-tests-final.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1]
    def esc(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = [f"""# 吉林大学全校网站通知适配验证专项

审计日期：2026-10-13（Asia/Shanghai）。报告生成：{summary.get('generated_at')}。

本轮完成官方目录清单建立和公开栏目有限抽样验证。结果不能作为“全校网站已支持”的声明，也不能替代 Cloud 生产运行或历史全量验收。没有修改正式 sources.yaml、执行策略、数据库模型或解析器，没有启动正式 crawler，没有提交 GitHub、发布 Release 或安装客户端。

## 1. 数量与统计口径

| 指标 | 数量 |
| --- | ---: |
| 官方目录、官网导航及补充证据对应的机构记录（含别名/多职能） | {summary.get('institution_rows')} |
| 去重机构名称 | {summary.get('distinct_institution_labels')} |
| 未提供/未确认独立官网的机构记录 | {summary.get('units_without_site')} |
| 规范化官网入口 URL | {summary.get('site_seed_urls')} |
| 官网主机名去重 | {summary.get('distinct_seed_hosts')} |
| 已完成入口发现检查 | {summary.get('site_discovery_completed')} |
| 有响应入口的最终 URL 去重 | {summary.get('distinct_final_site_urls')} |
| 有响应入口的最终主机名去重 | {summary.get('distinct_final_site_hosts')} |
| 规范化去重后的候选栏目/引用入口 | {summary.get('distinct_columns')} |
| 已检测的适配对象 | {summary.get('columns_checked')} |
| 未检测的适配对象 | {summary.get('columns_unchecked')} |
| 无需适配（范围外引用或单篇文章；不是已支持） | {summary.get('no_adaptation_needed')} |
| 完全通过（仅本轮样本） | {states.get('完全通过', 0)} |
| 部分通过 | {states.get('部分通过', 0)} |
| 失败/访问检查受阻 | {states.get('失败', 0)} |
| 需认证 | {states.get('需认证', 0)} |
| 最终清单保留的详情样本记录（允许缓存复用） | {summary.get('sampled_details')} |
| 最终清单保留的附件端点检查记录 | {summary.get('attachment_endpoints_checked')} |
| 最终清单保留的下一页检查记录 | {summary.get('pagination_pages_checked')} |
| 跨栏目同 URL 组 | {summary.get('same_url_duplicate_groups')} |
| 不同 URL 同规范标题/日期候选组 | {summary.get('title_date_duplicate_candidates')} |

首轮 326 个候选入口均已尝试验证；合并 {alias_count} 个有证据的路径/传输别名重复后保留 {summary.get('distinct_columns')} 个入口，其中 {summary.get('no_adaptation_needed')} 个是无需适配的单篇文章或范围外引用。机构、网站、栏目分别计数，不能相加计算覆盖率。一个机构可能有多个站点；同一站点可能服务多个机构。主机名不同的别名不在没有证据时强行合并，HTTP/HTTPS 只有实际跳转、相同页面哈希或字符等价证据才合并。已检测 + 未检测 + 无需适配 = 候选入口总数。失败包括抓取受阻，不能一概解释成解析器不兼容。问题标签可重叠，其数量不能相加当成失败总数。

`jlu-site-inventory.csv` 的 `record_type` 区分 institution/site/column；`jlu-compatibility-report.csv` 每个规范化候选栏目一行，含原 URL、检查时间、原因、发现依据和逐项证据文件。空数值代表该步未执行或未获得可报告值，0 代表执行后确为零。既有栏目标记“既有正式配置；本轮回归结果”，其他行标记“未登记支持；仅审计结果”；本轮没有新增支持登记。

## 2. 代码审计结论

1. `backend/config/sources.yaml` 有 7 个来源：6 个吉大官方来源共 8 个已配置栏目，以及个人本地蓝桥杯单页监控。蓝桥杯不属于全校通知栏目范围，本轮不运行其个人监控或写入 baseline。
2. `app/sources/registry.py` 构建来源。CSE、CCST、CSW、本科生院、创新创业学院都是 `StaticHTMLSource` 的薄子类，共用 `app/parsers/html.py`；没有各学院独立的通用补救规则。OA 是独立公开适配器，使用 Struts 列表/详情、相对日期和 OA 附件引用解析。
3. 通用列表按 `.list`、`.news_list` 等选择器回退至 `ul li a`，以 `info/` 或 .htm/.html 判断文章。空栏目可能误抓导航；就业网 `/portal/jyzp/article/details?id=...` 不满足现有规则。列表日期对整个 li/tr 搜索完整日期，会遗漏拆分日期，并可能读到摘要中的活动/公示日期。
4. 通用详情只识别 h1/.article-title/.title，正文优先 `.v_news_content`、`#vsb_content` 等，最终可回退整页 body。校级站的 `.nr_title` 和其他模板不在标题规则内。附件扩展名只覆盖 pdf/doc/docx/xls/xlsx/zip；图片附件、rar/7z/ppt 等需要后续明确范围。VSB download.jsp 返回 HTML 时不能认定附件已下载。
5. `app/api/source_management.py` 的 preview 使用 GenericPublicSource，取至多 3 条详情。当前成功条件主要是解析出非空样本，不验证页面语义、日期对照、附件下载及历史覆盖，因此“预览成功”不是本专项验收标准。高级配置支持选择器和 next_page_selector，受 source_max_pages（默认 3）限制；未配置时默认 1 页。StaticHTMLSource 本身只抓配置的首屏，每栏目最多 30 条。
6. `CrawlerManager` 负责入库、增量跳过、baseline、关系及健康状态，来源并发默认 2。本专项不实例化/启动它。去重优先 public_id、canonical_url；通常按 source_id 限制标题匹配，OA 配置 dedup_across_sources=true。精确标题匹配有 14 天窗口；近似匹配阈值 0.92，检查最近 300 条。跨站转载的相同标题是候选，不能直接合并；不同 URL 的转载、HTTP/HTTPS 别名和模板标题污染可能影响去重。
7. `_sync_sources` 对缺省 ownership 的官方配置归为 OFFICIAL_CLOUD。Desktop 优先 CloudFeedSource，官方 cloud_preferred 只有规定的 Cloud feed 错误才允许已配置本地 fallback；SHARED_CLOUD 默认 cloud_only，个人来源 local_only。Cloud 只执行云所有权来源，遵守 enabled、cloud_policy 和间隔。本轮只测公开原站解析，不把本机结果外推成实际 Cloud feed 成功。
8. SafeFetcher 保留逐跳 URL 校验、大小上限、重定向上限和 TLS 校验；Local 允许系统代理/Fake-IP 的域名解析语义，Cloud 保留严格 DNS/IP/peer 边界。StaticHTMLSource 的静态正式来源路径没有相同的逐跳通用 URL/大小约束，后续扩展不能绕过 GenericPublicSource 的安全边界。审计网络统一经过 SafeFetcher 包装，未更改这两条产品路径。
9. TLS 使用当前工作区工厂：Windows truststore + certifi，非 Windows 保持 certifi。此前 TLS 报告不是本轮全校验收证据；本机证书链能构建也不等于 Linux Cloud 能构建。证书失败不降级、不关闭验证。
10. 现有测试覆盖 parser fixtures、OA、source preview/选择器、安全、Cloud/本地 fallback、去重、数据库迁移、增量、保留策略和 TLS。本轮完整回归最终结果：**{tests}**。早期测试环境覆盖引起 4 个默认设置断言失败；工作区同时变化期间另有 6 个新增 HTTP 诊断测试失败，后续独立 7 项和完整回归均通过。保留原日志，不用早期结果替代最终基线。前端未改动，本轮不重复 UI 测试。

审计以当前工作区为准。开始时已存在 TLS、前端等未提交改动，过程中另有 HTTP 诊断代码/测试变化，全部保留。解析验证代码指纹见 `jlu-audit-evidence/validation-code-manifest.json`；最终指纹复核见验收记录。相关背景已读取 UI_AUDIT、Gate 13/14 架构与 Fake-IP/TLS 报告；本专项不改变 UI 或跨入后续实现 Gate。

收尾时另一个同期专项的 [OA_SOURCE_ERROR_REPORT.md](OA_SOURCE_ERROR_REPORT.md) 已记录：默认域名路径 TLS EOF、独立以太网定向访问成功、旧 certifi 路径链验证失败及 Cloud feed 未配置。该报告的定向 socket/临时路由实验不属于本专项；本轮未更改出口或复用它作为 OA 的通过证据。这里的 OA 仍按匿名默认路径实际受阻记录。SafeFetcher 当前仍可能把空消息异常压成 `Source request failed:`，故本轮未将这些不完整错误擅自判成超时或证书失败。

## 3. 官方发现依据和执行方法

从学校官网的 [管理、服务与业务机构](https://www.jlu.edu.cn/jgsz/gl_fwyywjg.htm)、[院系设置](https://www.jlu.edu.cn/jgsz/yxsz.htm)、[研究机构](https://www.jlu.edu.cn/jgsz/yjjg.htm)、[附属单位及校管企业](https://www.jlu.edu.cn/jgsz/fsdwjxgqy.htm) 提取真实链接与未链接名称。补充 [官网通知](https://www.jlu.edu.cn/index/tzgg.htm)、[学工处通知](https://xsc.jlu.edu.cn/index/tzgg.htm)、[就业网公开列表](https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg) 及官方页面证实的附属学校站点。每条发现依据保存在 CSV 与 supplemental-seeds.json，没有暴力扫描或猜测子域名。

先完成代码审计和四类目录/站点/栏目清单，再冻结清单执行批量预览。每站只看首页及最多六个一级教学、学工、科研等入口；保留被数量上限排除的入口。除官方目录和补充种子外不无限递归遍历。目录里的研究平台分组标题不计机构，未链接研究机构仍保留待确认；混合机构段落的未链接名称保留原样，不擅自拆解组织关系。

请求串行，全局至少 1 秒、同 origin 至少 1.2 秒，遵守更长 robots Crawl-delay；每请求 12 秒超时，瞬时故障最多两次尝试，证书/401/403/429/禁止规则不重试。robots 404/410 可继续；不可读取 robots 时保守停止，记录受阻而不推测规则。HTTP 目录入口失效时仅尝试同主机 HTTPS，保留原失败证据，不降级 HTTPS。遇登录、验证码或访问控制不操作、不绕过。

复用 GenericPublicSource.fetch_list/fetch_detail 与已配置来源纯解析方法，网络改由同一限速缓存提供；不调用带入库副作用的 crawler/API。P0/P1 取前两条详情，其他栏目取第一条；详情失败也记录。对照 DOM 的文章链接、标题/文档标题、独立发布日期标记、正文容器、可见附件；至多跟随一页分页。附件最多读取首个文件端点的 1 KiB，识别 HTML/空响应，其他文件明确未检查。OA 编码附件需要 POST 的链路本轮不执行，不能声称附件通过。

“完全通过”只表示本轮已检查样本没有发现问题。存在缺日期、标题截断/不一致、正文回退、附件未核验、分页不完整等任一项即部分通过；空结果、明显导航误抓、正文导航污染或所有详情失败即失败。单页 VSB 的禁用下页按钮会复核为单页，避免误报“分页未解析”。栏目外全国平台和单篇文章引用排除适配；URL 百分号别名去重记录见 url-aliases.json。可疑漏抓列表只作为待复核候选，因为旁栏文章可能不属于目标栏目。

## 4. 网站发现状态

| 状态 | 入口数 | 解释 |
| --- | ---: | --- |
"""]
    meanings = {"reachable": "发现了候选栏目，尚不等于兼容", "unreachable": "网络、TLS、robots 或访问限制受阻", "no_column_discovered": "限定发现范围内未找到栏目，不等于站点无通知", "authentication_required": "返回登录页/认证表单"}
    for state, count in summary.get("site_states", {}).items():
        lines.append(f"| {state} | {count} | {meanings.get(state, state)} |\n")
    lines.append("\n### 无法访问或规则受阻的入口\n\n| URL | 时间 | 原因 |\n| --- | --- | --- |\n")
    for d in discovery:
        if d["status"] in {"unreachable", "authentication_required"}:
            lines.append(f"| {esc(d['site_url'])} | {d.get('checked_at')} | {esc(d.get('reason', ''))} |\n")
    lines.append("\n## 5. 现有来源与校级通知回归\n\n以下仅代表原站本轮样本，Cloud feed 与已安装客户端另列未验证。\n\n| 栏目 | URL | 列表数 | 详情样本数 | 结果 | 问题/证据 |\n| --- | --- | ---: | ---: | --- | --- |\n")
    for r in results:
        if r.get("configured_source") or r["column_url"] == "https://www.jlu.edu.cn/index/tzgg.htm":
            count = "未执行" if r.get("list_count") is None else r.get("list_count", "")
            lines.append(f"| {esc(r.get('institution'))} / {esc(r.get('column'))} | {esc(r['column_url'])} | {count} | {len(r.get('details', []))} | {r['status']} | {esc(r['reason'])}；[{Path(r.get('evidence_file', '')).name}]({r.get('evidence_file', '').removeprefix('docs/')}) |\n")
    lines.append("\n## 6. 问题分类与复现证据\n\n每个栏目的全部标签、时间和快照在兼容性 CSV 与对应 JSON 中；这里按问题类型各列至多两个样例，标签数允许重叠。\n\n| 问题 | 栏目数 | 样例 URL |\n| --- | ---: | --- |\n")
    for issue, count in sorted(summary.get("issue_counts", {}).items(), key=lambda p: -p[1]):
        examples = [r["column_url"] for r in results if issue in r.get("issues", [])][:2]
        lines.append(f"| {issue} | {count} | {esc('；'.join(examples))} |\n")
    lines.append(r"""
### 已人工对照的关键现象

- 计算机教学通知 `https://ccst.jlu.edu.cn/info/1056/21217.htm`：列表/详情标题及 2026-10-10 日期一致，正文 716 字符，可见 docx 已提取；下载端点 `wbfileid=18207182` 的 Range 请求返回 206、`text/html;charset=UTF-8`、HTML 文件头，不能计为附件下载通过。没有绕过下载页验证。
- 校级通知 `https://www.jlu.edu.cn/info/1095/58176.htm`：完整标题在 `.nr_title`，列表末尾有省略号，通用标题选择器未命中而保留截断标题。应补模板标题选择器；不能把“返回非空标题”当正确。
- 学工 `https://xsc.jlu.edu.cn/info/1048/5941.htm`：详情发布日期为 2026-10-13；列表日期分为日与年月，摘要出现公示期 2026-10-12，通用 li 全文搜索错误取后者。应绑定日期节点并组合年月日，不从摘要取第一个日期。
- 软件教办 `https://csw.jlu.edu.cn/info/1095/8548.htm`：有六个 jpg 的 download.jsp 附件引用，通用附件扩展名规则均未输出。图片型成绩公示需要明确附件/图片内容呈现方案。
- 就业网通知、公示原页是公开服务端 HTML，存在 `/portal/jyzp/article/details?id=...` 标题链接与“创建时间”，不是只靠浏览器渲染才可见；通用规则未识别该 URL 类型而返回空列表。
- 多个空栏目回退 `ul li a` 后把 .htm 导航当文章，出现 30 条“候选”。例如汽车招生、公共计算机党建、历史文化部分栏目，详情又回退 body，构成可复现的预览假成功风险。
- 附中实验学校 `jdgz.jlu.edu.cn` 的 TLS 返回证书有效期校验失败原始异常，未关闭验证。图书馆入口因 robots 禁止而未继续访问，不能判为解析失败或无需适配。

复现时以本地快照与请求时间为准；搜索工具可能返回旧缓存或超时，不能用它覆盖真实匿名抓取结果。报告不附完整正文摘录，必要摘要与 HTML SHA-256 在逐项证据里。

## 7. 可复用规则与后续实现建议

| 模板/机制 | 复用方向 | 验收条件 |
| --- | --- | --- |
| VSB 普通列表与 `.v_news_content` / `#vsb_content` | 先复用现有 GenericPublicSource，按站点配置列表容器、标题和日期节点 | 空栏目为零、排除导航、至少三条详情比对；列表/详情日期一致 |
| VSB 分拆日期（学工、招生、部分学院） | 合成年/月/日，限定在日期元素；详情使用发布元信息 | 跨月跨年、摘要含截止日期也不能影响发布日期 |
| 校级 `.nr_title` 及学院不同标题容器 | 明确选择器并从标题节点剔除元信息 | 截断列表标题必须恢复全文，不将栏目名当通知标题 |
| VSB download.jsp / 图片附件 | 保留 filename/url/type；扩展名白名单需明确图片/压缩包/演示文件范围；区分下载页与二进制 | 不绕验证码，受限附件明确标记，不能以 200/206 当可下载 |
| VSB `.p_next a` / 禁用 `.p_next_d` | 使用现有 next_page_selector 与 1–3 页上限，页间 URL 去重 | 首次历史覆盖与日常增量分别验收，单页按钮禁用不误报 |
| 吉林大学就业网 SSR 列表 | 公开 details?id 链接、独立创建时间与内容容器的选择器/小型适配器 | 通知、公示、招聘、实习分别限定栏目；保持 id/query 的身份语义 |
| 公开 OA | 保留专用 Struts、相对日期及附件编码规则 | 本地与实际 Cloud 各自验收；POST 附件链路另开受限验证，不纳入本轮已通过 |
| 非 VSB/动态平台、重定向链较长 | 先确认公开 API 或服务端 HTML，再评估现有 api/selector 适配 | 不提高安全上限来掩盖登录跳转；需要认证时保持 local_only 的既有策略 |

本轮没有将建议写入正式来源。后续每批先加脱敏 fixture 与失败复现，再实现最小规则，离线测试、原站抽样、Cloud 环境和不污染正式 DB 的增量/去重回归通过后，才逐条登记支持。

## 8. 分级待适配方案

- **P0**：先闭环 OA 原站访问回归受阻、校级标题截断、现有 CSE 空正文及既有来源附件可用性。为通用 preview 加语义门槛，禁止导航/body 回退假成功流入正式来源。保持 cloud_preferred/fallback 条件和既有数据库身份。
- **P1**：学工日期节点、就业网 details?id 规则、本科/研究生招生、教务、科研和团委。优先用高级选择器验证高价值栏目，补一页受限分页和附件证据，再决定是否需要新 adapter。
- **P2**：按 CMS 模板批量复用各学院公开通知规则；先修误抓导航、错误标题和图片附件，再扩大栏目。已发现列表引用旁栏不能直接归为漏抓。
- **P3**：研究机构、医院、附属学校与校管企业。先确认官方链接/组织归属与 robots；未知官网、证书失败、站点消失分别处理，不用子域名猜测填满覆盖率。

具体待办按 CSV 的 priority/status/issues 排序，每个栏目都有可复现证据，不以机构级别的一个样本代替全部栏目验收。

## 9. 重复通知与覆盖边界

`duplicates.json` 分开保留跨栏目同 URL 与不同 URL 同标题/日期候选，只统计通过/部分通过列表，排除导航误抓和范围外引用。同 URL 重复发布通常可复用现有 canonical_url/关系去重；标题/日期重复可能是转载，也可能是不同对象的同名通知。正文一致性、目标人群及来源身份未充分对照前，不算数据库重复缺陷、不执行合并。数据仅来自本轮首屏，不能统计全校历史重复率。

未覆盖：无独立官网链接的机构；robots/网络/TLS/认证受阻入口；每站超过六个一级入口及更深页面；名称不含发现关键词的栏目；仅微信/公众号/内网发布；历史全部分页与历史详情；每栏目样本以外的附件和图片 OCR；OA 的附件 POST；受限系统；真实 Cloud Linux/PostgreSQL/feed 调度与安装客户端。没有条件证明无通知的网站不标无需适配。公开学术/新闻栏目混合通知时需要后续产品范围复核。

本轮因限速和有限递归而具有明确边界，不宣称穷尽所有官方站点。需认证数为本轮实际观测，不能解释成全校没有认证栏目。不能从兼容性样本计算“全校支持率”。

## 10. 证据、续检与验证

- [网站与栏目清单](jlu-site-inventory.csv)、[逐栏兼容性报告](jlu-compatibility-report.csv)。
- `jlu-audit-evidence/requests.json`：URL、原检查时间、重试次数、错误/HTTP、最终 URL、编码替换字符和快照 SHA-256。
- `http.jsonl`：每次实际响应元数据，不保存 Cookie/Authorization；网络无响应的异常在 requests.json。
- `html/`：公开页面快照；`results/`：逐栏详情对照、附件前缀/响应类型、分页及原因；`results.json` 汇总。
- `retry-history.json`、`pre-recheck-results.json`：有限重检前后证据；`review-decisions.json`：排除范围/单页/标题复核；`duplicates.json`：重复候选。
- 后端测试日志保留在 evidence；独立审计器有 7 项离线检查，覆盖错误标题、导航正文、附件漏抓、更多链接、分页与 OA URL 规范化。

```powershell
# 先审计/建清单，验证阶段只读；缓存存在时从断点继续。
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py discover
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py validate
# 可选有限瞬时故障重检，每 URL 累计尝试上限二次。
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py recheck
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py validate
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py review
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py report
```

缓存的失败不会无限重试，成功记录保留原检查时间而非伪装成重新联网。要建立新日期的独立审计，应使用新证据目录/另行规划，不覆盖本轮历史。CSV 为 UTF-8 BOM，中文可直接导入 Excel；长原因和 URL 保持完整。
""")
    tls_results = load_json(EVIDENCE / "tls-certifi.json", [])
    if tls_results:
        lines.append("\n### 本机 TLS 对照（不代表 Cloud 生产）\n\n| 来源 | certifi-only | Cloud DNS 策略对照 | 错误 |\n| --- | --- | --- | --- |\n")
        for t in tls_results:
            lines.append(f"| {t['source']} | {t['ok']} | {esc(t.get('cloud_dns_policy'))} | {esc(t.get('error', ''))} |\n")
    (OUTPUT_DOCS / "JLU_SITE_AUDIT.md").write_text("".join(lines), encoding="utf-8")
    print("Report written: docs/JLU_SITE_AUDIT.md", flush=True)


def finalize():
    """Offline integrity, metadata and reproducibility checks."""
    requests = load_json(EVIDENCE / "requests.json", {})
    results = load_json(EVIDENCE / "results.json", [])
    for r in results:
        if not r.get("list_snapshot") and not r.get("parser"):
            # A failed robots/network gate did not run a list parser. Unknown
            # counts must not appear as a verified empty list.
            r["list_count"] = None
            r["generic_count"] = None
            response = requests.get(norm(r["column_url"]), {})
            if response.get("status"):
                r["http_status"] = response["status"]
            if r.get("evidence_file"):
                save_json(ROOT / r["evidence_file"], r)
    save_json(EVIDENCE / "results.json", results)
    manifest = load_json(EVIDENCE / "validation-code-manifest.json", {})
    checks = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha for name, sha in manifest.get("files", {}).items()}
    assert all(checks.values()), "Audited application code changed; revalidation is required"
    assert len({r["column_url"] for r in results}) == len(results)
    assert all(r.get("checked_at") and r.get("reason") and (ROOT / r["evidence_file"]).exists() for r in results)
    restored = []
    for value in requests.values():
        if value.get("html_path"):
            file = EVIDENCE / value["html_path"]
            payload = file.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if digest != value["sha256"]:
                # Windows text-mode output translated LF to CRLF. Reverse that
                # exact transformation only when the original response-text
                # hash proves byte-for-byte restoration; never alter evidence
                # merely to force a new hash to match.
                original = payload.replace(b"\r\n", b"\n")
                assert hashlib.sha256(original).hexdigest() == value["sha256"], value["url"]
                file.write_bytes(original)
                restored.append({"file": value["html_path"], "saved_text_mode_sha256": digest,
                                 "restored_response_text_sha256": value["sha256"], "time": now()})
            assert hashlib.sha256(file.read_bytes()).hexdigest() == value["sha256"]
    if restored:
        save_json(EVIDENCE / "snapshot-newline-restoration.json", restored)
    export()
    summary = load_json(EVIDENCE / "summary.json", {})
    assert summary["columns_checked"] + summary["columns_unchecked"] + summary["no_adaptation_needed"] == summary["distinct_columns"]
    save_json(EVIDENCE / "acceptance.json", {"time": now(), "application_fingerprints_unchanged": checks,
              "evidence_checks": "URL uniqueness, timestamps, reasons, per-column files, every HTML SHA256, totals reconciled",
              "formal_database_used": False, "formal_sources_modified": False,
              "production_cloud_verified": False, "network_in_finalize": False,
              "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    report()
    print("Final evidence integrity checks passed", flush=True)


async def main():
    global EVIDENCE, OUTPUT_DOCS
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["directories", "discover", "validate", "export", "tls", "check", "recheck", "review", "report", "finalize"])
    parser.add_argument("--output-dir", help="Independent run directory under docs; original evidence stays unchanged")
    parser.add_argument("--input-dir", help="Copy only discovery metadata from an earlier run, never HTTP caches/results")
    parser.add_argument("--column-url", action="append", default=[], help="Validate only selected discovered columns; repeatable")
    args = parser.parse_args()
    if (args.input_dir or args.column_url) and not args.output_dir:
        parser.error("--input-dir / --column-url require an independent --output-dir")
    if args.output_dir:
        destination = (ROOT / args.output_dir).resolve()
        docs = (ROOT / "docs").resolve()
        historical = (docs / "jlu-audit-evidence").resolve()
        if not destination.is_relative_to(docs) or destination == docs or destination == historical or destination.is_relative_to(historical):
            parser.error("--output-dir must be a separate subdirectory of docs, outside historical evidence")
        if args.phase in {"review", "report", "finalize", "recheck"}:
            parser.error("This historical post-processing phase is unavailable for independent runs")
        EVIDENCE = OUTPUT_DOCS = destination
        os.environ["JLU_APP_DATA_DIR"] = str(EVIDENCE / "runtime")
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        if args.input_dir:
            source = (ROOT / args.input_dir).resolve()
            if source == destination or not source.is_relative_to(docs):
                parser.error("--input-dir must be a different evidence directory under docs")
            for name in ["columns.json", "units.json", "sites.json", "discovery.json", "supplemental-seeds.json"]:
                if not (EVIDENCE / name).exists() and (source / name).exists():
                    save_json(EVIDENCE / name, load_json(source / name, []))
        if args.column_url:
            columns = load_json(EVIDENCE / "columns.json", [])
            selected = {norm(url) for url in args.column_url}
            missing = selected - {norm(c["column_url"]) for c in columns}
            if missing:
                parser.error(f"URLs are not discovered columns: {sorted(missing)}")
            save_json(EVIDENCE / "columns.json", [c for c in columns if norm(c["column_url"]) in selected])
        save_json(EVIDENCE / "run.json", dict(time=now(), phase=args.phase, output=str(EVIDENCE),
                  discovery_input=args.input_dir, column_urls=args.column_url, mode="fresh HTTP run with same-run resume; no imported request cache"))
    fetch = AuditFetch()
    try:
        if args.phase == "directories":
            await directories(fetch)
        elif args.phase == "discover":
            await discover(fetch)
        elif args.phase == "validate":
            await validate(fetch)
        elif args.phase == "export":
            export()
        elif args.phase == "tls":
            await tls_check(fetch)
        elif args.phase == "check":
            self_check()
        elif args.phase == "recheck":
            await recheck(fetch)
        elif args.phase == "review":
            review()
        elif args.phase == "report":
            report()
        elif args.phase == "finalize":
            finalize()
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
