"""Validate all P2 entries with bounded public previews and isolated sample replay."""
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
from app.parsers.html import CONTENT_SELECTORS, in_navigation, is_empty_notice_list
from app.schemas.notice import NoticeCandidate
from app.services.dates import parse_date
from app.services.normalization import canonicalize_url, normalize_whitespace
from app.sources.base import SourceError
from app.sources.generic import GenericPublicSource
from validate_jlu_b5_c import database_rounds, inspect_detail

NEXT = '.p_pages .p_next a, a.Next:-soup-contains("下页"), .paging-arrow.xicon-right[href]'


def compact(record):
    return {k: v for k, v in record.items() if k != "html"}


def hospital_config(url):
    path = urlsplit(url).path
    match = re.fullmatch(r"/wujiaquery_g7yU_(\d+)\.html", path)
    route = "/wujia_detail_g7yU_" + match[1] + "/" if match else "/tongzhiy/detail_g7yU_91/"
    return {"pagination_limit": 2, "next_page_selector": NEXT,
            "item_selector": f'.list > .li:has(> a[href^="{route}"])',
            "title_selector": "a > .p", "url_selector": f'a[href^="{route}"]', "time_selector": "a > .y"}


def independent_urls(html, url):
    soup = BeautifulSoup(html, "html.parser")
    if urlsplit(url).hostname == "www.zrlyyy.com":
        nodes = soup.select(".list > .li > a[href]")
        nodes = [n for n in nodes if re.search(r"/(?:wujia_detail_g7yU_\d+|tongzhiy/detail_g7yU_\d+)/\d+\.html$", n["href"])]
    else:
        nodes = []
        for n in soup.select("a[href]"):
            if in_navigation(n) or "wburl" in str(n.get("onclick") or ""):
                continue
            href = urljoin(url, n["href"].strip())
            row = n.find_parent(["li", "tr"])
            dated_static = urlsplit(url).hostname != "law.jlu.edu.cn" and row and re.search(r"\.html?(?:[?#]|$)", href) and re.search(r"20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}", audit.text(row))
            query = parse_qs(urlsplit(href).query)
            observed_vsb_query = urlsplit(href).path.endswith(".jsp") and query.get("urltype") == ["news.NewsContentUrl"] and all(len(query.get(k, [])) == 1 and query[k][0].isdigit() for k in ["wbtreeid", "wbnewsid"])
            if re.search(r"/info/[^/]+/[^/]+\.html?(?:[?#]|$)", href) or dated_static or observed_vsb_query:
                nodes.append(n)
    return sorted({canonicalize_url(urljoin(url, n["href"].strip())) for n in nodes})


def compare(html, url, parsed):
    comparison = inspect_detail(html, url, parsed)
    soup = BeautifulSoup(html, "html.parser")
    body = next((soup.select_one(s) for s in CONTENT_SELECTORS if soup.select_one(s) is not None), None)
    form = (body.find_parent("form", attrs={"name": "_newscontent_fromname"}) or body.find_parent(class_="neirong")) if body else None
    if form is None and body is not None and body.find_parent(id="vsb_content"):
        form = body.find_parent(id="vsb_content").parent
    if form:
        before_body = {id(n) for n in body.previous_elements}
        headings = [n for n in form.select("h1,h2,h3,h4,h5,h6,.tittle,.title,.news_nr1,.tittle_con,.title2,.tit,.cont_title") if n is not body and id(n) in before_body and body not in n.parents and body not in n.descendants and not in_navigation(n)]
        if any(audit.text(n) == parsed.title for n in headings):
            comparison["title_verified"] = True
            comparison["additional_scoped_heading_evidence"] = [audit.text(n) for n in headings]
            comparison["issues"] = [i for i in comparison["issues"] if i != "TITLE_NOT_INDEPENDENTLY_VERIFIED"]
        publication = []
        for n in form.select("div,p,span,i,h2,h3,h4,h5,h6"):
            if n is body or body in n.parents or body in n.descendants or in_navigation(n):
                continue
            label = audit.text(n)
            if len(label) <= 300:
                match = re.search(r"(?<![\u4e00-\u9fff])(?:发布日期|发布时间|发表时间|发表于|日期)[：:\s]*(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}日?)", label)
                if match is None and n.get("class") and any(k in n["class"] for k in ["info", "zzly"]):
                    match = re.search(r"时间[：:\s]*(20\d{2}[-/.年]\s*\d{1,2}[-/.月]\s*\d{1,2}日?)", label)
                if match:
                    publication.append({"text": label, "date": str(parse_date(match[1]) or "")})
        unique_dates = {p["date"] for p in publication if p["date"]}
        if len(unique_dates) == 1 and str(parsed.publish_date or "") in unique_dates:
            comparison["date_verified"] = True
            comparison["additional_publication_evidence"] = publication
            comparison["issues"] = [i for i in comparison["issues"] if i != "DATE_NOT_INDEPENDENTLY_VERIFIED"]
    # This CMS has an explicitly scoped heading/publication line/body.
    if urlsplit(url).hostname == "www.zrlyyy.com":
        heading, meta, body = (soup.select_one(s) for s in [".article_details1 .cont > .title", ".article_details1 .liner", ".article_details1 .cont > .text"])
        if heading is not None and meta is not None and body is not None:
            date_match = re.search(r"发布时间[：:]\s*(20\d{2}\.\d{2}\.\d{2})", audit.text(meta))
            observed_text = parsed.content
            image_urls = []
            for image in body.select("img[src]"):
                target = urljoin(url, image["src"])
                if urlsplit(target).hostname == urlsplit(url).hostname and not any(str(image.get(k, "")).isdigit() and int(image[k]) < 32 for k in ["width", "height"]):
                    image_urls.append(target)
                    observed_text = observed_text.replace(target, " ")
            comparison.update(title_verified=audit.text(heading) == parsed.title,
                date_verified=bool(date_match and parse_date(date_match[1]) == parsed.publish_date),
                body_verified=normalize_whitespace(body.get_text(" ", strip=True)) == normalize_whitespace(observed_text) and all(u in parsed.content for u in image_urls),
                reference_body_image_urls=image_urls, image_downloads=0, ocr_verified=False,
                reference_titles=[audit.text(heading)], reference_dates=[date_match[0]] if date_match else [])
            expected = {urljoin(url, n["href"]) for n in body.select("a[href]") if
                        re.search(r"\.(?:pdf|docx?|xlsx?|zip|rar|7z|pptx?|jpe?g|png)(?:[?#]|$)", urljoin(url, n["href"]), re.I)}
            comparison.update(reference_attachment_urls=sorted(expected),
                missing_attachment_urls=sorted(expected - {a.url for a in parsed.attachments}),
                attachments_verified=expected == {a.url for a in parsed.attachments})
            comparison["issues"] = [k.upper() + "_NOT_INDEPENDENTLY_VERIFIED" for k in ["title", "date", "body", "attachments"] if not comparison[k + "_verified"]]
    comparison["source_replacement_characters"] = html.count("\ufffd")
    if comparison["source_replacement_characters"]:
        comparison["issues"].append("ENCODING_REPLACEMENT_IN_SOURCE")
    return comparison


def empty_evidence(html):
    soup = BeautifulSoup(html, "html.parser")
    proofs = []
    for node in soup.select(".pb_sys_common, #datalist .empty-data, .p_t"):
        raw = str(node)
        if re.search(r"共\s*0\s*条|暂无数据|暂无通知|暂无信息|_simple_list_gotopage_fun\(0\s*,", raw):
            proofs.append({"text": audit.text(node)[:240], "html": raw[:2500]})
    return proofs


async def validate(fetch, target, out):
    row = {**target, "checked_at": audit.now(), "details": [], "pages": [], "enabled": False,
           "formal_admission": False, "cloud_production_verified": False, "complete_download_verified": False,
           "history_verified": False, "status": "待验证", "verdict": "NOT_VERIFIED", "reason": ""}
    url = target["url"]
    if urlsplit(url).hostname == "oa.jlu.edu.cn":
        row.update(status="无需作为公开栏目适配", verdict="LOGIN_REFERENCE_OA_DEFERRED", reason="Original target is OA login; user deferred OA work; zero requests")
        return row
    first = await fetch.get(url)
    row["response"] = compact(first)
    if not first.get("ok") or first.get("auth"):
        row.update(status="受阻", verdict="ACCESS_BLOCKED", reason=first.get("error", "AUTH_REQUIRED"))
        return row
    html, final = first["html"], first["final_url"]
    if re.search("没有访问当前栏目的权限|无权访问当前栏目", html):
        row.update(status="权限受限", verdict="PERMISSION_RESTRICTED", reason="Explicit column permission denial; no login/bypass attempted")
        return row
    if urlsplit(final).hostname != urlsplit(url).hostname:
        row.update(verdict="REDIRECT_SCOPE_REVIEW", reason="Final hostname differs; no further article requests")
        return row
    if re.fullmatch(r"/wujia_detail_g7yU_\d+/\d+\.html", urlsplit(url).path):
        soup = BeautifulSoup(html, "html.parser")
        frame = soup.select_one(".article_details1")
        row.update(status="无需作为栏目适配", verdict="SINGLE_ARTICLE_REFERENCE", reason="Scoped article title/publication/body and original parent listing prove this is one article", reference_title=audit.text(frame.select_one(".title")) if frame else "", parent_column=target["discovery_url"])
        return row
    soup = BeautifulSoup(html, "html.parser")
    if url == "https://math.jlu.edu.cn/zsjy/bkszs/zsx.htm" and soup.select_one(".sec-fr .article > h3") and soup.select_one(".sec-fr .article [id^='vsb_content_']"):
        row.update(status="无需作为栏目适配", verdict="STATIC_INFORMATION_PAGE", reason="This section embeds one admissions information article, with no chronological notice list", reference_title=audit.text(soup.select_one(".sec-fr .article > h3")), publication_date_verified=False)
        return row
    if canonicalize_url(url) == canonicalize_url(target["site_url"]):
        row.update(verdict="HOMEPAGE_SCOPE_REVIEW", reason="Homepage is a mixed directory; a bounded notice section needs an explicit product scope")
        return row
    if is_empty_notice_list(html):
        row.update(status="当前空栏目", verdict="VERIFIED_EMPTY_COLUMN", reason="Explicit server-rendered zero-record/pager evidence, no fabricated notices", empty_evidence=empty_evidence(html))
        return row
    if url == "https://auto.jlu.edu.cn/zsxx.htm":
        soup = BeautifulSoup(html, "html.parser")
        children = [{"title": audit.text(a), "url": urljoin(final, a["href"])} for a in soup.select(".left > ul > li > a[href]")]
        if len(children) == 4 and not independent_urls(html, final):
            row.update(status="无需作为栏目适配", verdict="SECTION_DIRECTORY_REFERENCE", reason="Admissions section directory links four sub-sections; it is not a notice list", child_sections_unverified=children)
            return row
    config = {**target["config"], "parser_config": {"pagination_limit": 2, "next_page_selector": NEXT, **target["config"].get("parser_config", {})}}
    if urlsplit(url).hostname == "www.zrlyyy.com":
        config["parser_config"] = hospital_config(url)
    row["config"] = config
    source = GenericPublicSource(config)
    await source.fetcher.close()
    class Preview:
        async def get(self, target_url):
            if urlsplit(target_url).hostname != urlsplit(url).hostname:
                raise SourceError("B6_CROSS_HOST_NOT_FETCHED")
            value = await fetch.get(target_url)
            if not value.get("ok") or value.get("auth"):
                raise SourceError(value.get("error", "AUTH_REQUIRED"))
            if urlsplit(value["final_url"]).hostname != urlsplit(url).hostname:
                raise SourceError("B6_CROSS_HOST_REDIRECT_NOT_ADMITTED")
            return value["html"], value["content_type"], value["final_url"]
        async def validate_url(self, target_url):
            return await fetch.fetcher.validate_url(target_url)
        async def close(self):
            pass
    source.fetcher = Preview()
    try:
        items = await source.fetch_list()
        row.update(items=[i.model_dump(mode="json") for i in items], list_count=len(items), pagination=source.pagination_report)
        expected = set()
        for page in source.pagination_report[0]["pages"]:
            saved = fetch.inflate(fetch.cache[audit.request_url(page["url"])])
            refs = independent_urls(saved["html"], saved["final_url"])
            next_refs = audit.page_next(saved["html"], saved["final_url"])
            if urlsplit(url).hostname == "www.zrlyyy.com":
                next_refs += [urljoin(saved["final_url"], n["href"]) for n in BeautifulSoup(saved["html"], "html.parser").select(".paging-arrow.xicon-right[href]")]
            row["pages"].append({"response": compact(saved), "reference_urls": refs, "observed_next_urls": next_refs})
            expected.update(refs)
        actual = {canonicalize_url(i.url) for i in items}
        row.update(missing_reference_urls=sorted(expected - actual), unexpected_urls=sorted(actual - expected),
                   pagination_verified=expected == actual and not (source.pagination_report[0]["stop_reason"] == "NO_NEXT_PAGE" and row["pages"][-1]["observed_next_urls"]))
        internal = [i for i in items if urlsplit(i.url).hostname == urlsplit(url).hostname]
        row["external_references_not_fetched"] = [i.url for i in items if i not in internal]
        if not internal and row["external_references_not_fetched"]:
            row.update(status="无需作为独立栏目适配", verdict="EXTERNAL_REFERENCE_DIRECTORY", reason="All entries point to other official sites; no independent same-site notices; cross-host details not fetched")
            return row
        selected = internal[:2]
        query_control = next((i for i in internal if "urltype=news.NewsContentUrl" in i.url and i not in selected), None)
        if query_control:
            selected.append(query_control)
        if len(row["pages"]) > 1:
            older = set(row["pages"][1]["reference_urls"]) - set(row["pages"][0]["reference_urls"])
            item = next((i for i in internal if canonicalize_url(i.url) in older and i not in selected), None)
            if item and len(selected) < 3:
                selected.append(item)
        for item in internal:
            if len(selected) >= 3:
                break
            if item not in selected:
                selected.append(item)
        samples = []
        for item in selected:
            detail = {"url": item.url, "list_title": item.title, "list_date": str(item.publish_date or "")}
            try:
                parsed = await source.fetch_detail(item)
                record = fetch.inflate(fetch.cache[audit.request_url(item.url)])
                comparison = compare(record["html"], record["final_url"], parsed)
                detail.update(response=compact(record), parsed=parsed.model_dump(mode="json"), comparison=comparison,
                              verified=not comparison["issues"] and all(comparison[k + "_verified"] for k in ["title", "date", "body", "attachments"]))
                samples.append(parsed)
            except (SourceError, ValueError) as exc:
                detail.update(reason=str(exc), verified=False, response=compact(fetch.cache.get(audit.request_url(item.url), {})))
            row["details"].append(detail)
        row["needed_details"] = min(3, len(internal))
        if samples:
            row["database_replay"] = await database_rounds(samples, target["id"], out / "test-runtime" / target["id"], retain_all_samples=True)
        good = row["pagination_verified"] and len(row["details"]) == row["needed_details"] > 0 and all(d["verified"] for d in row["details"]) and row.get("database_replay", {}).get("passed") and not row.get("database_replay", {}).get("unexpected_merge_requires_review")
        row.update(status="部分通过" if good else "待修复或证据不足", verdict="BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN" if good else "SAMPLE_REVIEW_REQUIRED",
                   reason="Independent list/detail/date/attachment DOM checks and isolated replay passed; file download, actual Cloud and full history unverified" if good else "See per-page/detail comparisons; candidate remains disabled")
    except (SourceError, ValueError) as exc:
        row.update(status="待修复或证据不足", verdict="LIST_OR_PAGINATION_UNSUPPORTED", reason=str(exc), pagination=getattr(source, "pagination_report", []))
    finally:
        await source.close()
    return row


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--input-dir", default="docs/jlu-fix-b6/discovery-20261015")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = audit.ROOT / "docs/jlu-fix-b6"
    out, inputs = (audit.ROOT / args.output_dir).resolve(), (audit.ROOT / args.input_dir).resolve()
    assert out.is_relative_to(root) and inputs.is_relative_to(root) and out != inputs
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    names = ["backend/scripts/validate_jlu_b6.py", "backend/scripts/validate_jlu_b5_c.py", "backend/scripts/validate_jlu_b4.py",
             "backend/scripts/audit_jlu_sites.py", "backend/app/parsers/html.py", "backend/app/sources/generic.py", "backend/app/sources/base.py",
             "backend/app/services/list_pagination.py", "backend/app/crawler/runner.py", "backend/app/services/deduplication.py",
             "backend/app/services/source_security.py", "backend/app/services/tls.py", "backend/config/sources.yaml", "docs/jlu-fix-b6/targets.json"]
    hashes = {p: hashlib.sha256((audit.ROOT / p).read_bytes()).hexdigest() for p in names}
    hashes.update({"input/" + n: hashlib.sha256((inputs / n).read_bytes()).hexdigest() for n in ["requests.json", "code-manifest.json"]})
    previous = audit.load_json(out / "code-manifest.json", {})
    assert not previous or (previous["files"] == hashes and previous["offline"] == args.offline), "Changed input/code; use a new directory"
    audit.save_json(out / "code-manifest.json", {"time": previous.get("time", audit.now()), "files": hashes, "offline": args.offline,
         "input_dir": str(inputs.relative_to(audit.ROOT)), "limits": "164 entries, <=2 pages and <=3 details each; serial robots/rate limits; no attachments downloaded",
         "database": "application engine connections forbidden; independent sample replay uses sqlite://"})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    attempts = []
    def reject(*args):
        attempts.append(audit.now())
        raise RuntimeError("B6_APPLICATION_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject)
    class Fetch(audit.AuditFetch):
        async def get(self, url, *args_, **kwargs):
            if args.offline and audit.request_url(url) not in self.cache:
                raise SourceError("OFFLINE_URL_NOT_CAPTURED: " + url)
            return await super().get(url, *args_, **kwargs)
    fetch = Fetch()
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
    old = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    results = []
    try:
        for target in sorted(audit.load_json(root / "targets.json", []), key=lambda t: t["old_status"] != "失败"):
            row = old.get(target["id"]) or await validate(fetch, target, out)
            results.append(row)
            audit.save_json(out / "results.json", results)
            print(len(results), target["institution"], target["column"], row["verdict"], row.get("list_count", 0), flush=True)
        assert not attempts
        if args.offline:
            assert not fetch.request_count
        details = [d for r in results for d in r["details"]]
        audit.save_json(out / "summary.json", {"time": audit.now(), "entries": len(results), "verdicts": dict(Counter(r["verdict"] for r in results)),
            "statuses": dict(Counter(r["status"] for r in results)), "details": len(details), "verified_details": sum(d["verified"] for d in details),
            "list_pages": sum(len(r["pages"]) for r in results), "list_items": sum(r.get("list_count", 0) for r in results),
            "isolated_replays": sum(r.get("database_replay", {}).get("passed", False) for r in results),
            "http_attempts_this_session": fetch.request_count, "requests_cached": len(fetch.cache), "application_db_connections": 0,
            "cloud_production_verified": False, "complete_downloads": 0, "oa_requests": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
