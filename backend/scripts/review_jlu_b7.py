"""Offline-only P3 acceptance replay; missing captures fail closed."""
import argparse
import asyncio
from collections import Counter
import hashlib
import os
import re
import shutil
from urllib.parse import parse_qs, urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.sources.base import SourceError
from app.services.dates import parse_date
from app.services.normalization import canonicalize_url
from app.parsers.html import CONTENT_SELECTORS, in_navigation
import validate_jlu_b6 as core
from validate_jlu_b6 import compact, validate

ROOT = audit.ROOT / "docs/jlu-fix-b7"
BASE_COMPARE = core.compare
BASE_REFERENCES = core.independent_urls

LIST_RULES = {
    "fszx.jlu.edu.cn": {"item_selector": "table.winstyle105920 tr:has(a.c105920)", "title_selector": "a.c105920", "url_selector": "a.c105920", "time_selector": ".timestyle105920"},
    "bjkg.jlu.edu.cn": {"item_selector": ".new_list3 dd[id^='line_']", "title_selector": "a.fl", "url_selector": "a.fl", "time_selector": "span.fr"},
    "pftheory.jlu.edu.cn": {"item_selector": ".view-content .list dl[id^='line_']", "title_selector": "dt > a", "url_selector": "dt > a", "time_selector": "dt .date-display-single"},
    "gjs.jlu.edu.cn": {"item_selector": "tr[id^='line_u2_']", "title_selector": "a.titles", "url_selector": "a.titles", "time_selector": ".pubtime"},
    "synlab.jlu.edu.cn": {"item_selector": "article.type-post.entry-list, article.type-post.entry-list-medium", "title_selector": "h2.entry-title-activities > a", "url_selector": "h2.entry-title-activities > a", "time_selector": "time.entry-date", "next_page_selector": "a.next.page-numbers"},
}
REFERENCE_RULES = {
    "fszx.jlu.edu.cn": "table.winstyle105920 a[href]",
    "bjkg.jlu.edu.cn": ".new_list3 dl > dd > a[href]",
    "pftheory.jlu.edu.cn": ".view-content .list dl > dt > a[href]",
    "gjs.jlu.edu.cn": "tr[id^='line_u2_'] td > a[href]",
    "zcgl.jlu.edu.cn": ".section-fr > ul.list a[href]",
    "synlab.jlu.edu.cn": "article.entry-list h2 > a[href],article.entry-list-medium h2 > a[href]",
}


def independent_urls(html, url):
    selector = REFERENCE_RULES.get(urlsplit(url).hostname)
    if selector is None:
        return BASE_REFERENCES(html, url)
    soup = BeautifulSoup(html, "html.parser")
    return sorted({canonicalize_url(urljoin(url, a["href"].strip())) for a in soup.select(selector)
                   if not in_navigation(a) and re.search(r"/(?:info/[^/]+/[^/]+\.html?|20\d{2}/\d{2}/\d+\.html)(?:[?#]|$)", urljoin(url, a["href"]))})


def compare(html, url, parsed):
    result = BASE_COMPARE(html, url, parsed)
    soup = BeautifulSoup(html, "html.parser")
    body = next((soup.select_one(s) for s in CONTENT_SELECTORS if soup.select_one(s) is not None), None)
    if body is None:
        return result
    frame = body.find_parent("form", attrs={"name": "_newscontent_fromname"}) or body.find_parent(class_="right-nr") or body.find_parent("article", class_="type-post")
    if frame is None and body.find_parent(id="vsb_content") and body.find_parent("td", class_="content"):
        frame = body.find_parent("td", class_="content").find_parent("table")
    if frame is None:
        return result
    before = {id(n) for n in body.previous_elements}
    titles = []
    for n in frame.select(".content-bt,.t > p.ti,.readtitle,.item_biaoti,p.biaoti,.abouttitle > p,.nav01 > h3,.view-title,.entry-header > h1.entry-title,.content > #Title,:scope > tr > td.title"):
        if id(n) in before and body not in n.descendants and body not in n.parents:
            titles.append({"tag": n.name, "classes": n.get("class", []), "text": audit.text(n)})
    if any(n["text"] == parsed.title for n in titles):
        result["title_verified"] = True
        result["independent_b7_header_titles"] = titles
    dates = []
    for n in frame.select(".t > .author > span,.view-info,.wzxxys,.nav01 > h6 .ll > span,:scope > h3 > span,.xiab > .xb1,.entry-header time.entry-date[datetime],:scope > div > h1 + div[align='center'],:scope > tr > td.pubtime_publisher"):
        if id(n) not in before or body in n.descendants or body in n.parents:
            continue
        label = str(n.get("datetime") or audit.text(n))
        if len(label) <= 300 and (n.has_attr("datetime") or re.fullmatch(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", label) or re.search(r"(?:发布时间|发布日期|时间)[：:]", label)) and not re.search("更新|修改|上传", label):
            value = parse_date(label)
            if value:
                dates.append({"text": label, "date": str(value)})
    if len({n["date"] for n in dates}) == 1 and dates[0]["date"] == str(parsed.publish_date or ""):
        result["date_verified"] = True
        result["independent_b7_publication_metadata"] = dates
    result["issues"] = [issue for issue in result["issues"] if issue not in {k.upper() + "_NOT_INDEPENDENTLY_VERIFIED" for k in ["title", "date"] if result[k + "_verified"]}]
    if frame.name == "article" and "type-post" in frame.get("class", []):
        expected = {urljoin(url, a["href"]) for a in body.select("a[href]") if re.search(r"\.(?:pdf|docx?|xlsx?|zip)(?:[?#]|$)", a["href"], re.I)}
        for footer in frame.select(":scope > footer"):
            if footer.select_one(":scope > h4") and re.fullmatch(r"相关附件[：:]\s*\d+", audit.text(footer.select_one(":scope > h4"))):
                expected.update(urljoin(url, a["href"]) for a in footer.select(":scope > ul:not(.tag-list) a[href]"))
        actual = {a.url for a in parsed.attachments}
        result.update(reference_attachment_urls=sorted(expected), missing_attachment_urls=sorted(expected - actual),
                      unexpected_attachment_urls=sorted(actual - expected), attachments_verified=actual == expected)
        result["issues"] = [i for i in result["issues"] if i != "ATTACHMENTS_NOT_INDEPENDENTLY_VERIFIED"]
        if actual != expected:
            result["issues"].append("ATTACHMENTS_NOT_INDEPENDENTLY_VERIFIED")
    return result


def scope_reference(target, response):
    if not response.get("ok") or response.get("auth"):
        return None
    soup = BeautifulSoup(response["html"], "html.parser")
    verdict, reason = "", ""
    static_recruitment = {
        "https://talent.jlu.edu.cn/rczp.htm": "系列层次",
        "https://jt.jlu.edu.cn/szdw/rczp.htm": "柔性引进系列",
        "https://press.jlu.edu.cn/lxwm/rczp.htm": "请关注吉林大学出版社官网",
    }
    if target["url"] in static_recruitment and static_recruitment[target["url"]] in soup.get_text() and not BASE_REFERENCES(response["html"], response["final_url"]):
        verdict, reason = "STATIC_RECRUITMENT_INFORMATION_PAGE", "Captured page is ongoing recruitment/contact information with no chronological article list or publication metadata; no list adaptation admission"
    if "COLUMN_IS_HOMEPAGE_NEEDS_SCOPE_REVIEW" in target.get("old_issues", ""):
        verdict, reason = "HOMEPAGE_SCOPE_REVIEW", "Original homepage mixes several sections; notice columns are validated separately, no automatic homepage admission"
    if urlsplit(target["url"]).hostname == "iiimct.jlu.edu.cn":
        observed = [{"title": audit.text(n), "url": urljoin(response["final_url"], n["href"])} for n in soup.select(".inner_s1 > ul > li > a.eclip[href]")]
        if observed and all(urlsplit(n["url"]).hostname == "mp.weixin.qq.com" for n in observed):
            verdict, reason = "EXTERNAL_PLATFORM_REFERENCES", "All four observed entries link to WeChat; no same-site details. Platform fetch/auth/download not attempted; not marked supported"
    if verdict:
        return {**target, "checked_at": audit.now(), "response": compact(response), "details": [], "pages": [], "enabled": False,
            "formal_admission": False, "cloud_production_verified": False, "complete_download_verified": False, "history_verified": False,
            "status": "范围待确认" if verdict == "HOMEPAGE_SCOPE_REVIEW" else "无需作为独立通知列表适配", "verdict": verdict, "reason": reason,
            "observed_external_references": observed if verdict == "EXTERNAL_PLATFORM_REFERENCES" else []}
    return None


def article_reference(target, response):
    """Classify only observed article routes, never infer a notice list from title."""
    p = urlsplit(target["url"])
    query = parse_qs(p.query)
    jsp = p.path.endswith(".jsp") and query.get("urltype") == ["news.NewsContentUrl"]
    dated = p.hostname == "synlab.jlu.edu.cn" and re.fullmatch(r"/20\d{2}/\d{2}/\d+\.html", p.path)
    if not (jsp or dated) or not response.get("ok") or response.get("auth"):
        return None
    soup = BeautifulSoup(response["html"], "html.parser")
    restricted = jsp and re.search("没有访问当前栏目的权限|无权访问当前栏目|无权访问此页面", response["html"])
    if jsp and soup.select_one("form[name='_newscontent_fromname']") is None and not restricted:
        return None
    return {**target, "response": compact(response), "checked_at": audit.now(), "details": [], "pages": [],
        "enabled": False, "formal_admission": False, "cloud_production_verified": False, "history_verified": False,
        "complete_download_verified": False, "status": "无需作为栏目适配", "verdict": "SINGLE_ARTICLE_REFERENCE",
        "reason": "Observed article route and saved page identify one article, not an independent notice list; not marked supported",
        "article_permission_restricted": bool(restricted),
        "reference_title": audit.text(soup.title) if soup.title else "", "discovery_url": target["discovery_url"]}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    inputs, out = [(audit.ROOT / name).resolve() for name in [args.input, args.output]]
    assert inputs != out and all(p.is_relative_to(ROOT) and p != ROOT for p in [inputs, out])
    assert (inputs / "summary.json").exists(), "Input capture must be complete"
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    names = ["backend/scripts/review_jlu_b7.py", "backend/scripts/validate_jlu_b6.py", "backend/scripts/validate_jlu_b5_c.py",
        "backend/scripts/validate_jlu_b4.py", "backend/scripts/audit_jlu_sites.py", "backend/app/parsers/html.py",
        "backend/app/services/deduplication.py", "backend/app/services/list_pagination.py", "backend/app/crawler/runner.py",
        "backend/app/sources/generic.py", "backend/app/sources/base.py", "backend/app/services/source_security.py", "backend/app/services/tls.py",
        "backend/config/sources.yaml"]
    hashes = {p: hashlib.sha256((audit.ROOT / p).read_bytes()).hexdigest() for p in names}
    hashes.update({"input/" + n: hashlib.sha256((inputs / n).read_bytes()).hexdigest() for n in ["requests.json", "validation-targets.json", "code-manifest.json"]})
    old = audit.load_json(out / "code-manifest.json", {})
    assert not old or old["files"] == hashes, "Preserve previous run; new output required"
    audit.save_json(out / "code-manifest.json", {"time": old.get("time", audit.now()), "files": hashes, "offline": True,
        "input_dir": str(inputs.relative_to(audit.ROOT)), "limits": "<=2 pages/3 details; offline missing URLs fail closed; zero network, no production DB"})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    def reject(*_):
        raise RuntimeError("B7_REVIEW_APPLICATION_DATABASE_FORBIDDEN")
    event.listen(engine, "connect", reject)
    class Fetch(audit.AuditFetch):
        async def get(self, url, *pos, **kw):
            if audit.request_url(url) not in self.cache:
                raise SourceError("OFFLINE_URL_NOT_CAPTURED: " + url)
            return await super().get(url, *pos, **kw)
    fetch = Fetch()
    core.compare, core.independent_urls = compare, independent_urls
    if not fetch.cache:
        for key, value in audit.load_json(inputs / "requests.json", {}).items():
            if value.get("html_path"):
                path = inputs / value["html_path"]
                assert hashlib.sha256(path.read_bytes()).hexdigest() == value["sha256"]
                dest = out / value["html_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
            fetch.cache[key] = value
        audit.save_json(out / "requests.json", fetch.cache)
    old_rows = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    rows = []
    try:
        for target in audit.load_json(inputs / "validation-targets.json", []):
            if target["id"].startswith("recruitment-") and "学院" in target["institution"]:
                target = {**target, "priority": "P2", "discovery_priority_correction": "College column discovered in B7, reported as P2; does not change original B6 scope"}
            rules = LIST_RULES.get(urlsplit(target["url"]).hostname)
            if rules:
                target = {**target, "config": {**target["config"], "parser_config": {**target["config"]["parser_config"], **rules}}}
            row = old_rows.get(target["id"])
            if row is None:
                response = await fetch.get(target["url"])
                row = article_reference(target, response) or scope_reference(target, response) or await validate(fetch, target, out)
                if row.get("pagination"):
                    stop = row["pagination"][0]["stop_reason"]
                    if stop not in {"PAGE_LIMIT", "ITEM_LIMIT", "NO_NEXT_PAGE", "DISABLED_NEXT_PAGE", "EMPTY_PAGE"}:
                        row["pagination_verified"] = False
                        if row["verdict"] == "BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN":
                            row.update(verdict="SAMPLE_REVIEW_REQUIRED", status="待修复或证据不足", reason="Pagination stopped at an unsupported/safety boundary: " + str(stop))
                    for page in row["pages"]:
                        saved = fetch.inflate(page["response"])
                        if urlsplit(target["url"]).hostname == "synlab.jlu.edu.cn":
                            page["observed_next_urls"] = sorted(set(page["observed_next_urls"]) | {urljoin(saved["final_url"], a["href"]) for a in BeautifulSoup(saved["html"], "html.parser").select("a.next.page-numbers[href]")})
            rows.append(row)
            audit.save_json(out / "results.json", rows)
            print(len(rows), target["institution"], row["verdict"], flush=True)
        assert fetch.request_count == 0
        details = [d for r in rows for d in r["details"]]
        audit.save_json(out / "summary.json", {"time": audit.now(), "entries": len(rows), "verdicts": dict(Counter(r["verdict"] for r in rows)),
            "details": len(details), "verified_details": sum(d["verified"] for d in details), "list_pages": sum(len(r["pages"]) for r in rows),
            "list_items": sum(r.get("list_count", 0) for r in rows), "isolated_replays": sum(r.get("database_replay", {}).get("passed", False) for r in rows),
            "http_attempts": 0, "application_db_connections": 0, "downloads": 0, "oa_requests": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
