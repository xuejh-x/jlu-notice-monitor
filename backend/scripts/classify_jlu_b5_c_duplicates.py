"""Reproduce original duplicate candidates and classify saved evidence offline."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
import audit_jlu_sites as audit
from app.parsers.html import CONTENT_SELECTORS
from app.services.normalization import canonicalize_url, normalize_title, normalize_whitespace

ROOT = audit.ROOT
OUT = ROOT / "docs/jlu-fix-b5-c"
ORIGINAL = ROOT / "docs/jlu-audit-evidence"


def signature(records):
    return tuple(sorted((r["column_url"], r["url"], r["title"], r["date"] or "") for r in records))


def main():
    original = audit.load_json(ORIGINAL / "duplicates.json", {})
    urls, titles, saved = defaultdict(list), defaultdict(list), {}
    files = {"docs/jlu-audit-evidence/" + name: hashlib.sha256((ORIGINAL / name).read_bytes()).hexdigest()
             for name in ["duplicates.json", "results.json"]}
    # The original export reads this reviewed aggregate. Per-column files
    # retain earlier observations and must not replace those review decisions.
    for result in audit.load_json(ORIGINAL / "results.json", []):
        for detail in result.get("details", []):
            if detail.get("snapshot"):
                saved.setdefault(canonicalize_url(detail["url"]), detail)
        if result.get("status") not in {"完全通过", "部分通过"} or "POSSIBLE_NAVIGATION_CAPTURE" in result.get("issues", []):
            continue
        for item in result.get("list_items", []):
            record = {"column_url": result["column_url"], "url": item["url"], "title": item["title"], "date": item["publish_date"]}
            urls[audit.norm(item["url"])].append(record)
            if item["publish_date"] and len(normalize_title(item["title"])) >= 8:
                titles[(normalize_title(item["title"]), item["publish_date"])].append(record)
    repeated = {url: rows for url, rows in urls.items() if len({r["column_url"] for r in rows}) > 1}
    candidates = [rows for rows in titles.values() if len({audit.norm(r["url"]) for r in rows}) > 1]
    assert {k: signature(v) for k, v in repeated.items()} == {k: signature(v) for k, v in original["same_url_groups"].items()}
    assert {signature(v) for v in candidates} == {signature(v) for v in original["title_date_candidates"]}
    assert len(repeated) == 113 and len(candidates) == 48
    body_cache = {}
    def body_evidence(url):
        key = canonicalize_url(url)
        if key in body_cache:
            return body_cache[key]
        detail = saved.get(key)
        if not detail:
            return {"url": url, "status": "NO_SAVED_DETAIL"}
        path = ORIGINAL / detail["snapshot"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == detail["sha256"]
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        body = next((soup.select_one(s) for s in CONTENT_SELECTORS if soup.select_one(s) is not None), None)
        value = {"url": url, "captured_at": detail["time"], "snapshot": "docs/jlu-audit-evidence/" + detail["snapshot"], "sha256": detail["sha256"]}
        if body:
            for n in body.select("script,style,noscript"):
                n.decompose()
            text = normalize_whitespace(body.get_text(" ", strip=True))
            value.update(status="SCOPED_TEXT_AVAILABLE" if text else "NO_SCOPED_TEXT", chars=len(text),
                         text_sha256=hashlib.sha256(text.encode()).hexdigest() if text else None)
        else:
            value["status"] = "NO_SUPPORTED_BODY_CONTAINER"
        body_cache[key] = value
        return value
    classified_urls = []
    for url, rows in repeated.items():
        canonical = {canonicalize_url(r["url"]) for r in rows}
        classified_urls.append({"group_url": url, "category": "SAME_URL_COLUMN_REFERENCE" if len(canonical) == 1 else "SOURCE_CANONICALIZER_ALIAS_REVIEW",
                                "records": rows, "canonical_urls": sorted(canonical), "database_duplicate_proven": False,
                                "action": "Reuse canonical identity and retain source relations; no production merge or deletion"})
    classified_titles = []
    for index, rows in enumerate(candidates):
        canonical = {canonicalize_url(r["url"]) for r in rows}
        scheme_free = {urlunsplit(urlsplit(u)._replace(scheme="", fragment="")) for u in canonical}
        hosts = {urlsplit(u).hostname for u in canonical}
        category = "CANONICAL_ALIAS_REFERENCE" if len(canonical) == 1 else "PROTOCOL_ALIAS_CANDIDATE" if len(scheme_free) == 1 else "CROSS_SITE_REPRINT_CANDIDATE" if len(hosts) > 1 else "SAME_SITE_DISTINCT_URL_CANDIDATE"
        bodies = [body_evidence(u) for u in sorted(canonical)]
        hashes = {b["text_sha256"] for b in bodies if b.get("text_sha256")}
        complete = all(b.get("text_sha256") for b in bodies)
        verdict = "MATCHING_SAVED_TEXT_REPRINT_EVIDENCE" if complete and len(hashes) == 1 else "DIFFERENT_SAVED_TEXT_REVIEW_REQUIRED" if complete else "INSUFFICIENT_SAVED_BODY_EVIDENCE"
        classified_titles.append({"index": index + 1, "category": category, "records": rows, "body_evidence": bodies,
                                  "body_verdict": verdict, "database_duplicate_proven": False, "automatic_merge_authorized": False,
                                  "action": "Keep source-scoped identity; matching heading/date alone does not justify cross-source merge"})
    summary = {"time": audit.now(), "mode": "offline reconstruction of original audit; no HTTP or DB", "original_counts_reproduced": True,
               "same_url_groups": len(classified_urls), "title_date_candidates": len(classified_titles),
               "same_url_categories": dict(Counter(g["category"] for g in classified_urls)),
               "title_date_categories": dict(Counter(g["category"] for g in classified_titles)),
               "saved_body_verdicts": dict(Counter(g["body_verdict"] for g in classified_titles)),
               "formal_merges": 0, "global_similarity_threshold_changed": False}
    audit.save_json(OUT / "duplicate-classification.json", {"summary": summary, "input_hashes": files,
                                                           "same_url_groups": classified_urls, "title_date_candidates": classified_titles})
    print(summary)


if __name__ == "__main__":
    main()
