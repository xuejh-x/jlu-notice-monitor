"""Read-only, serial B4 previews using disabled candidates and existing sources."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from urllib.parse import urljoin, urlsplit
import re
from types import SimpleNamespace

from bs4 import BeautifulSoup

import audit_jlu_sites as audit
from probe_jlu_b3 import PrefixAudit
from app.parsers.html import CONTENT_SELECTORS, in_navigation, is_empty_notice_list
from app.services.dates import parse_date
from app.services.normalization import normalize_whitespace
from app.services.source_security import validate_local_source_url
from app.sources.base import SourceError
from app.sources.generic import GenericPublicSource


def inspect_sample(html, url, parsed):
    """Cross-check scoped DOM evidence, not status/nonempty alone."""
    soup = BeautifulSoup(html, "html.parser")
    body = next((soup.select_one(s) for s in CONTENT_SELECTORS if soup.select_one(s) is not None), None)
    evidence = {"title_verified": False, "date_verified": False, "body_verified": False,
                "attachments_verified": False, "reference_titles": [], "reference_dates": [], "issues": []}
    updated_times = []
    for selector in [".m-detail-container__title", ".detail_head1", "form[name='_newscontent_fromname'] h2.tit",
                     "form[name='_newscontent_fromname'] h2[align='center']", ".nr_title", ".art-tit h3", ".detail-title", ".detail-tit h4",
                     "form[name='_newscontent_fromname'] > .bt", ".article-title", "form[name='_newscontent_fromname'] h1", "h1.title"]:
        for heading in soup.select(selector):
            if in_navigation(heading) or heading is body or (body is not None and body in heading.parents):
                continue
            clone = BeautifulSoup(str(heading), "html.parser")
            for tag in list(clone.select("script,style,.meta")):
                tag.decompose()
            if selector == ".nr_title":
                for tag in list(clone.select("span")):
                    if re.match(r"^(作者|时间|来源|点击数)[：:]", tag.get_text(strip=True)):
                        tag.decompose()
            title = normalize_whitespace(clone.get_text(" ", strip=True))
            evidence["reference_titles"].append({"selector": selector, "title": title})
            if parsed.title == title and title:
                evidence["title_verified"] = True
    if body is not None:
        frame = body.find_parent("form", attrs={"name": "_newscontent_fromname"}) or body.parent
        for node in frame.select("span,p,.m-detail-container__info,.meta,.sub,.xq,.xiab,.detail-infor,.conttime,.title11,.arc-info"):
            if node is body or body in node.parents or body in node.descendants or in_navigation(node):
                continue
            label = normalize_whitespace(node.get_text(" ", strip=True))
            if len(label) < 300 and "更新时间：" in label:
                updated = parse_date(label)
                if updated:
                    updated_times.append(str(updated))
            if len(label) > 300 or not re.search(r"(?:^|[^\u4e00-\u9fff])(?:发布日期|发布时间|发表时间|创建时间|日期|时间)[：:]", label):
                continue
            date = parse_date(label)
            if date:
                evidence["reference_dates"].append({"text": label, "date": str(date)})
                if date == parsed.publish_date:
                    evidence["date_verified"] = True
        if not evidence["date_verified"] and updated_times:
            evidence["date_semantics"] = "UPDATE_TIME_ONLY_PUBLICATION_UNCONFIRMED"
            evidence["reference_update_times"] = sorted(set(updated_times))
        clone = BeautifulSoup(str(body), "html.parser")
        for tag in list(clone.select("script,style,noscript")):
            tag.decompose()
        reference_text = normalize_whitespace(clone.get_text(" ", strip=True))
        evidence["body_reference_chars"] = len(reference_text)
        observed_text = parsed.content
        for img in body.select("img[src]"):
            observed_text = observed_text.replace(urljoin(url, str(img["src"])), " ")
        observed_text = normalize_whitespace(observed_text)
        evidence["body_verified"] = bool(reference_text and reference_text == observed_text)
        if not reference_text and body.select("img[src]"):
            images = [urljoin(url, str(img["src"])) for img in body.select("img[src]")]
            evidence["body_verified"] = any(image in parsed.content for image in images)
        expected = set()
        for anchor in frame.select("a[href]"):
            if in_navigation(anchor):
                continue
            target = urljoin(url, anchor["href"])
            text = anchor.get_text(" ", strip=True)
            if "news.DownloadAttachUrl" in target or "/portal/common/downloadFile?" in target or re.search(r"\.(pdf|docx?|xlsx?|zip)(?:[?\s]|$)", target + " " + text, re.I):
                expected.add(target)
        actual = {a.url for a in parsed.attachments}
        evidence["reference_attachment_urls"] = sorted(expected)
        evidence["missing_attachment_urls"] = sorted(expected - actual)
        evidence["attachments_verified"] = not (expected - actual)
    for key in ["title", "date", "body", "attachments"]:
        if not evidence[key + "_verified"]:
            evidence["issues"].append("SITE_DATE_IS_UPDATE_TIME" if key == "date" and updated_times else key.upper() + "_NOT_INDEPENDENTLY_VERIFIED")
    return evidence


async def validate(fetch, candidate):
    config = candidate["config"]
    assert config["enabled"] is False and config["auth_type"] == "none" and not config["allow_private_network"]
    url = config["base_url"]
    listing = await fetch.get(url)
    result = {"id": candidate["id"], "institution": candidate["institution"], "column": candidate["column"],
              "url": url, "captured_at": listing["time"], "validated_at": audit.now(), "status": "失败",
              "verdict": "NOT_ADMITTED", "enabled": False, "details": [], "issues": [], "attachment_probes": [],
              "cloud_production_verified": False, "history_verified": False,
              "discovery_url": candidate["discovery_url"], "reason": ""}
    if not listing.get("ok") or listing.get("auth"):
        category = audit.error_category(listing)
        result.update(status="需认证" if category == "AUTH_REQUIRED" else "失败", verdict="ACCESS_BLOCKED",
                      issues=[category], reason=listing.get("error", "Authentication required"))
        return result
    result.update(final_url=listing["final_url"], list_snapshot=listing["html_path"], list_sha256=listing["sha256"], http_status=listing["status"])
    if re.search(r"没有访问当前栏目的权限|无权访问当前栏目", listing["html"]):
        result.update(status="需认证", verdict="PERMISSION_RESTRICTED", issues=["COLUMN_PERMISSION_REQUIRED"],
                      reason="Page explicitly denies column permission; login requirements not confirmed, no bypass attempted")
        return result
    if urlsplit(listing["final_url"]).hostname != urlsplit(url).hostname:
        result.update(verdict="REDIRECT_SCOPE_REVIEW", issues=["REDIRECTED_TO_OTHER_SITE"], reason="Final host differs; no article preview or promotion")
        return result
    source = GenericPublicSource(config)
    original_fetcher = source.fetcher
    class PreviewFetcher:
        async def get(self, target):
            value = await fetch.get(target)
            if not value.get("ok") or value.get("auth"):
                raise SourceError(value.get("error", "AUTH_REQUIRED"))
            return value["html"], value["content_type"], value["final_url"]
        async def validate_url(self, target):
            return await fetch.fetcher.validate_url(target)
        async def close(self):
            pass
    source.fetcher = PreviewFetcher()
    try:
        try:
            items = await source.fetch_list()
        except (SourceError, ValueError) as exc:
            empty = is_empty_notice_list(listing["html"])
            result.update(verdict="EMPTY_COLUMN_NO_DETAIL_ACCEPTANCE" if empty else "LIST_UNSUPPORTED",
                          status="待验收" if empty else "失败", issues=["VERIFIED_EMPTY_COLUMN" if empty else "LIST_PARSE_ERROR"], reason=str(exc))
            return result
        result["list_items"] = [item.model_dump(mode="json") for item in items]
        result["list_count"] = len(items)
        external = [item.url for item in items if urlsplit(item.url).hostname != urlsplit(url).hostname]
        result["external_references_not_fetched"] = external
        internal = [item for item in items if item.url not in external]
        if external:
            result["issues"].append("EXTERNAL_REFERENCES_REQUIRE_SCOPE_RULE")
        if not internal:
            result.update(verdict="NO_INTERNAL_NOTICE_SAMPLE", reason="No same-site notice to verify")
            return result
        selected = internal[:3]
        # If the first three contain no file, inspect at most two more. Never
        # claim the remaining notices have no attachments.
        with_files = []
        index = 0
        while index < len(selected):
            item = selected[index]
            d = {"url": item.url, "list_title": item.title, "list_date": str(item.publish_date or "")}
            try:
                parsed = await source.fetch_detail(item)
                saved = fetch.cache.get(audit.norm(item.url), {})
                html = fetch.inflate(saved).get("html", "")
                d.update(captured_at=saved.get("time"), snapshot=saved.get("html_path"), sha256=saved.get("sha256"),
                         title=parsed.title, date=str(parsed.publish_date or ""), content_chars=len(parsed.content),
                         content_sha256=hashlib.sha256(parsed.content.encode()).hexdigest(), content_preview=parsed.content[:300],
                         attachments=[a.model_dump() for a in parsed.attachments])
                d.update(inspect_sample(html, saved.get("final_url", item.url), parsed))
                if parsed.attachments:
                    with_files.extend(parsed.attachments)
            except (SourceError, ValueError) as exc:
                saved = fetch.cache.get(audit.norm(item.url), {})
                d.update(captured_at=saved.get("time"), snapshot=saved.get("html_path"), sha256=saved.get("sha256"),
                         issues=["DETAIL_PREVIEW_REJECTED"], reason=str(exc))
            result["details"].append(d)
            index += 1
            if index == len(selected) and not with_files and len(selected) < min(len(internal), 5):
                selected.append(internal[len(selected)])
        if with_files:
            attachment = with_files[0]
            probe = await fetch.probe(attachment.url, attachment.type)
            result["attachment_probes"].append(dict(probe, filename=attachment.filename, type=attachment.type))
            if not probe.get("file_prefix_verified"):
                result["issues"].append("ATTACHMENT_" + probe["category"])
            if len({a.url for a in with_files}) > 1:
                result["issues"].append("REMAINING_ATTACHMENTS_UNCHECKED")
        else:
            result["issues"].append("NO_ATTACHMENT_IN_BOUNDED_SAMPLE")
        result["pagination"] = {"observed_next_urls": audit.page_next(listing["html"], listing["final_url"]), "checked": False, "max_pages": 1}
        result["issues"].append("HISTORY_AND_CLOUD_NOT_VERIFIED")
        good = [d for d in result["details"] if not d.get("issues")]
        structural = [d for d in result["details"] if set(d.get("issues", [])) <= {"SITE_DATE_IS_UPDATE_TIME"}]
        result["verified_details"] = len(good)
        result["structurally_verified_details"] = len(structural)
        needed = min(3, len(internal))
        result["all_available_checked"] = len(result["details"]) == len(internal)
        if len(good) >= needed and all(not d.get("issues") for d in result["details"]):
            result.update(status="部分通过", verdict="CONTENT_SAMPLE_PASSED" if not external else "CONTENT_PASSED_SCOPE_REVIEW_REQUIRED")
        elif len(structural) >= needed and len(structural) == len(result["details"]):
            result.update(status="部分通过", verdict="CONTENT_PASSED_DATE_SEMANTICS_REVIEW_REQUIRED")
        else:
            result.update(status="失败", verdict="CONTENT_SAMPLE_NOT_VERIFIED")
        result["reason"] = "; ".join(result["issues"] + sorted({issue for d in result["details"] for issue in d.get("issues", [])}))
        return result
    finally:
        await original_fetcher.close()
        await source.close()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--review-input-dir", help="Explicit offline review of prior live snapshots; no new HTTP")
    args = parser.parse_args()
    out = (audit.ROOT / args.output_dir).resolve()
    assert out.is_relative_to(audit.ROOT / "docs/jlu-fix-b4") and out != audit.ROOT / "docs/jlu-fix-b4"
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    inputs = audit.ROOT / "docs/jlu-fix-b4/source-candidates.json"
    candidates = json.loads(inputs.read_text(encoding="utf-8"))
    files = ["backend/app/parsers/html.py", "backend/app/sources/generic.py", "backend/app/sources/base.py",
             "backend/app/services/attachment_validation.py", "backend/app/services/tls.py", "backend/app/services/source_security.py",
             "backend/scripts/audit_jlu_sites.py", "backend/scripts/probe_jlu_b3.py", "backend/scripts/validate_jlu_b4.py"]
    fingerprints = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    fingerprints[inputs.relative_to(audit.ROOT).as_posix()] = hashlib.sha256(inputs.read_bytes()).hexdigest()
    mode = "offline_review" if args.review_input_dir else "live"
    fingerprints["validation_mode"] = hashlib.sha256((mode + str(args.review_input_dir)).encode()).hexdigest()
    if args.review_input_dir:
        review_source = (audit.ROOT / args.review_input_dir).resolve()
        assert review_source.is_relative_to(audit.ROOT / "docs/jlu-fix-b4") and review_source != out
        for filename in ["requests.json", "code-manifest.json"]:
            fingerprints["review-input/" + filename] = hashlib.sha256((review_source / filename).read_bytes()).hexdigest()
    previous = audit.load_json(out / "code-manifest.json", {})
    if (out / "results.json").exists() and previous.get("files") != fingerprints:
        raise RuntimeError("Candidate/code fingerprint changed; choose a new output directory")
    audit.save_json(out / "code-manifest.json", {"time": audit.now(), "files": fingerprints, "database": "sqlite://", "mode": mode,
                    "execution": "one serial process; existing GenericPublicSource preview; disabled candidates"})
    audit.save_json(out / "review-mode.json", {"mode": mode, "input": args.review_input_dir, "time": audit.now()})
    old = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    results = []
    if args.review_input_dir:
        source_dir = (audit.ROOT / args.review_input_dir).resolve()
        assert source_dir.is_relative_to(audit.ROOT / "docs/jlu-fix-b4") and source_dir != out
        class OfflineFetch:
            def __init__(self):
                self.cache = audit.load_json(source_dir / "requests.json", {})
                self.fetcher = SimpleNamespace(validate_url=lambda url: validate_local_source_url(url, allow_private_network=False))
            async def get(self, url):
                value = dict(self.cache.get(audit.norm(url), {}))
                if not value:
                    raise SourceError("OFFLINE_SNAPSHOT_MISSING: " + url)
                if value.get("html_path"):
                    raw = (source_dir / value["html_path"]).read_bytes()
                    assert hashlib.sha256(raw).hexdigest() == value["sha256"]
                    path = out / value["html_path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                    value["html"] = raw.decode("utf-8")
                return value
            def inflate(self, value):
                value = dict(value)
                if value.get("html_path"):
                    value["html"] = (source_dir / value["html_path"]).read_bytes().decode("utf-8")
                return value
            async def probe(self, url, kind):
                value = dict(self.cache.get("b3-prefix:" + url, {"url": url, "category": "NOT_RECHECKED", "file_prefix_verified": False,
                             "reason": "No saved prefix; no HTTP allowed during offline review"}))
                if value.get("prefix_path"):
                    raw = (source_dir / value["prefix_path"]).read_bytes()
                    assert hashlib.sha256(raw).hexdigest() == value["prefix_sha256"]
                    path = out / value["prefix_path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                return value
            async def close(self):
                pass
        fetch = OfflineFetch()
    else:
        fetch = PrefixAudit()
    try:
        for candidate in candidates:
            if candidate["id"] in old:
                results.append(old[candidate["id"]])
                continue
            print("CANDIDATE", candidate["id"], candidate["config"]["base_url"], flush=True)
            result = await validate(fetch, candidate)
            path = out / "results" / (candidate["id"] + ".json")
            result["evidence_file"] = path.relative_to(audit.ROOT).as_posix()
            audit.save_json(path, result)
            results.append(result)
            audit.save_json(out / "results.json", results)
            print(result["status"], result["verdict"], result.get("list_count", 0), result.get("verified_details", 0), flush=True)
        fields = ["id", "institution", "column", "url", "captured_at", "validated_at", "status", "verdict", "enabled", "list_count",
                  "verified_details", "cloud_production_verified", "history_verified", "reason", "evidence_file"]
        with (out / "compatibility-report.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        groups = defaultdict(list)
        for r in results:
            for item in r.get("list_items", []):
                groups[item["url"]].append(r["id"])
        audit.save_json(out / "overlaps.json", {url: sorted(set(ids)) for url, ids in groups.items() if len(set(ids)) > 1})
        summary = {"time": audit.now(), "mode": mode, "input": args.review_input_dir, "candidates": len(candidates), "checked": len(results),
                   "states": dict(Counter(r["status"] for r in results)), "verdicts": dict(Counter(r["verdict"] for r in results)),
                   "details_attempted": sum(len(r["details"]) for r in results), "verified_details": sum(r.get("verified_details", 0) for r in results),
                   "attachment_endpoints": sum(len(r["attachment_probes"]) for r in results), "formal_sources_changed": 0}
        audit.save_json(out / "summary.json", summary)
        print(summary, flush=True)
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
