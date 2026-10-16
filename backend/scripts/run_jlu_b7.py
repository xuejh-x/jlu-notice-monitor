"""Bounded, serial, resumable official discovery and P3 preview; no production DB."""
import argparse
import asyncio
from collections import Counter
import hashlib
import os
import re
from urllib.parse import urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.services.normalization import canonicalize_url
from app.sources.base import SourceError
from discover_jlu_b6 import inspect
from validate_jlu_b6 import compact, validate

ROOT = audit.ROOT / "docs/jlu-fix-b7"
HUB = re.compile(r"^(?:" + audit.HUB.pattern.strip("^$") + r"|新闻动态|中心动态|机构设置|研究机构|相关链接|友情链接|关于我们|招标采购|通知公示)$")


def links(html, base):
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for a in soup.select("a[href]"):
        href = a["href"].strip()
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        url = urljoin(base, href)
        p = urlsplit(url)
        if p.scheme in {"http", "https"} and not (p.username or p.password):
            result.append({"label": audit.text(a), "url": audit.request_url(url), "parent_text": audit.text(a.parent)[:180]})
    return result


def failure(record):
    message = record.get("error", "")
    # Nested errors retain their root cause rather than all becoming robots/TLS.
    for token in ["ROBOTS_DISALLOWED", "TLS_CERTIFICATE_VERIFY_FAILED", "ACCESS_RESTRICTED_HTTP_403",
                  "ACCESS_RESTRICTED_HTTP_429", "ACCESS_RESTRICTED_HTTP_401"]:
        if token in message:
            return token
    if "Server disconnected" in message:
        return "SERVER_DISCONNECTED"
    if "Timeout" in message:
        return "TIMEOUT"
    if record.get("status") == 404:
        return "HTTP_404"
    if record.get("auth"):
        return "AUTH_REQUIRED"
    return "ROBOTS_UNAVAILABLE_OTHER" if "ROBOTS_UNAVAILABLE" in message else "ACCESS_OTHER"


def unit_matches(units, anchors):
    results = []
    for index, unit in enumerate(units):
        exact = [a for a in anchors if re.sub(r"\s+", "", a["label"]) == re.sub(r"\s+", "", unit["institution"])
                 and not re.search(r"/info/|news.NewsContentUrl|\.(?:pdf|docx?|xlsx?|zip)$", a["url"])]
        candidates = []
        for a in exact:
            if a["url"] not in {x["url"] for x in candidates}:
                candidates.append(a)
        results.append({**unit, "row_id": index + 1, "review_time": audit.now(), "observed_links": candidates,
            "status": "OFFICIAL_EXACT_LINK_FOUND_NEEDS_SITE_VERIFICATION" if candidates else "OFFICIAL_SITE_UNCONFIRMED",
            "reason": "Exact institution label on a captured official page; target identity/content still require validation" if candidates
                      else "No exact official hyperlink in four directories, main navigation and bounded related pages; no domain guessed",
            "independent_site_verified": False, "no_adaptation_needed": False})
    return results


async def discovery(fetch, out):
    anchors = []
    directory_rows = []
    for category, url in [*audit.DIRECTORIES.items(), ("校级主页", "https://www.jlu.edu.cn/")]:
        response = await fetch.get(url)
        directory_rows.append({"category": category, "response": compact(response)})
        if response.get("ok") and not response.get("auth"):
            soup = BeautifulSoup(response["html"], "html.parser")
            frame = soup.select_one("#vsb_content") if category != "校级主页" else soup
            if frame is not None:
                anchors += [{**a, "discovery_url": response["final_url"], "snapshot": response["html_path"], "capture_time": response["time"]}
                            for a in links(str(frame), response["final_url"])]
    audit.save_json(out / "directories.json", directory_rows)
    previous = {r["site_url"]: r for r in audit.load_json(out / "site-results.json", [])}
    results = []
    columns = {}
    for old in audit.load_json(ROOT / "discovery-targets.json", []):
        url = old["site_url"]
        row = previous.get(url)
        if row is None:
            row = {"site_url": url, "institutions": old["institutions"], "categories": old["categories"],
                   "original_state": old["status"], "original_reason": old.get("reason", ""), "checked_at": audit.now(),
                   "original_discovery_urls": old.get("discovery_urls", []), "pages": [], "columns": [], "omitted_hubs": []}
            if urlsplit(url).hostname == "oa.jlu.edu.cn":
                row.update(verdict="DEFERRED_OA_BY_USER", reason="No requests; user deferred OA", response=None)
            else:
                # Reuse the previously observed alternate, never invent a domain or downgrade HTTPS.
                request = old.get("alternate_url") or url
                response = await fetch.get(request)
                row["response"] = compact(response)
                if not response.get("ok") or response.get("auth"):
                    row.update(verdict=failure(response), reason=response.get("error", "AUTH_REQUIRED"))
                else:
                    row.update(verdict="NO_COLUMN_FOUND_WITHIN_BOUND", reason="Homepage and <=3 explicit related hubs; absence is not proof of no notices")
                    pages = [response]
                    observed = links(response["html"], response["final_url"])
                    hubs = []
                    for a in observed:
                        if HUB.fullmatch(a["label"]) and urlsplit(a["url"]).hostname == urlsplit(response["final_url"]).hostname and canonicalize_url(a["url"]) != canonicalize_url(response["final_url"]) and a["url"] not in hubs:
                            hubs.append(a["url"])
                    row["omitted_hubs"] = hubs[3:]
                    for hub in hubs[:3]:
                        child = await fetch.get(hub)
                        row["pages"].append(compact(child))
                        if child.get("ok") and not child.get("auth"):
                            pages.append(child)
                    for page in pages:
                        for a in links(page["html"], page["final_url"]):
                            anchors.append({**a, "discovery_url": page["final_url"], "snapshot": page["html_path"], "capture_time": page["time"]})
                        for link, label in audit.column_links(page["html"], page["final_url"]).items():
                            # Recover exact observed href: canonical identity is never an HTTP request target.
                            actual = next((a["url"] for a in links(page["html"], page["final_url"]) if audit.norm(a["url"]) == link), link)
                            column = {"url": actual, "column": label, "institution": " / ".join(old["institutions"]),
                                      "site_url": url, "discovery_url": page["final_url"], "discovery_snapshot": page["html_path"],
                                      "capture_time": page["time"], "priority": min(audit.priority(n, cat) for n in old["institutions"] for cat in old["categories"])}
                            row["columns"].append(column)
                    if row["columns"]:
                        row.update(verdict="COLUMN_LINKS_FOUND_NEED_VALIDATION", reason="Official page labels/hrefs found; not yet supported")
        results.append(row)
        for col in row["columns"]:
            columns.setdefault(canonicalize_url(col["url"]), col)
        audit.save_json(out / "site-results.json", results)
        print("SITE", len(results), url, row["verdict"], len(row["columns"]), flush=True)
    # Also inspect official homepages of failed P3 entries to prove stale/replacement links.
    failed_homes = []
    for target in audit.load_json(ROOT / "targets.json", []):
        if target["old_status"] == "失败" and target["site_url"] not in failed_homes:
            failed_homes.append(target["site_url"])
    home_rows = []
    for url in failed_homes:
        if urlsplit(url).hostname == "oa.jlu.edu.cn":
            continue
        response = await fetch.get(url)
        row = {"url": url, "response": compact(response), "columns": []}
        if response.get("ok") and not response.get("auth"):
            row["columns"] = [{"url": u, "column": n} for u, n in audit.column_links(response["html"], response["final_url"]).items()]
            anchors += [{**a, "discovery_url": response["final_url"], "snapshot": response["html_path"], "capture_time": response["time"]}
                        for a in links(response["html"], response["final_url"])]
        home_rows.append(row)
    audit.save_json(out / "failed-homepages.json", home_rows)
    audit.save_json(out / "observed-anchors.json", anchors)
    audit.save_json(out / "unknown-units.json", unit_matches(audit.load_json(ROOT / "unknown-unit-targets.json", []), anchors))
    audit.save_json(out / "discovered-columns.json", list(columns.values()))
    audit.save_json(out / "discovery-summary.json", {"time": audit.now(), "sites": len(results), "directories": len(directory_rows),
        "verdicts": dict(Counter(r["verdict"] for r in results)), "discovered_columns": len(columns),
        "observed_anchors": len(anchors), "http_attempts_process": fetch.request_count, "oa_requests": 0,
        "application_db_connections": 0, "downloads": 0})


def validation_targets(out):
    targets = audit.load_json(ROOT / "targets.json", [])
    known = {canonicalize_url(r["column_url"]) for r in __import__("csv").DictReader((audit.ROOT / "docs/jlu-compatibility-report.csv").open(encoding="utf-8-sig"))}
    new = [c for c in audit.load_json(out / "discovered-columns.json", []) if canonicalize_url(c["url"]) not in known]
    new.sort(key=lambda c: (c["priority"], c["url"]))
    audit.save_json(out / "new-columns-not-selected.json", [{**c, "reason": "New-column bound 40; discovery only, not supported"} for c in new[40:]])
    for column in new[:40]:
        key = hashlib.sha256(column["url"].encode()).hexdigest()[:12]
        targets.append({**column, "id": "new-" + key, "old_status": "新发现未验证", "old_issues": "", "original_evidence": "",
            "config": {"code": "candidate-jlu-b7-" + key, "name": column["institution"] + " / " + column["column"],
                "base_url": column["url"], "parser": "generic_html", "enabled": False, "auth_type": "none",
                "allow_private_network": False, "validation_scope": "local", "execution_policy": "cloud_preferred",
                "parser_config": {"pagination_limit": 2}}})
    return targets


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=["discovery", "validation", "all"], default="all")
    args = parser.parse_args()
    out = (audit.ROOT / args.output).resolve()
    assert out.is_relative_to(ROOT) and out != ROOT
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    names = ["backend/scripts/run_jlu_b7.py", "backend/scripts/validate_jlu_b6.py", "backend/scripts/validate_jlu_b5_c.py",
             "backend/scripts/audit_jlu_sites.py", "backend/app/parsers/html.py", "backend/app/services/deduplication.py",
             "backend/app/sources/generic.py", "backend/app/sources/base.py", "backend/app/services/source_security.py",
             "backend/app/services/tls.py", "backend/config/sources.yaml", "docs/jlu-fix-b7/targets.json", "docs/jlu-fix-b7/discovery-targets.json"]
    hashes = {n: hashlib.sha256((audit.ROOT / n).read_bytes()).hexdigest() for n in names}
    old = audit.load_json(out / "code-manifest.json", {})
    assert not old or old["files"] == hashes, "Changed code/inputs; choose a new output"
    audit.save_json(out / "code-manifest.json", {"time": old.get("time", audit.now()), "files": hashes, "database": "sqlite:// independent replay only",
        "limits": "serial >=1s global >=1.2s origin/robots; 12s timeout, <=2 transient attempts; 59 sites <=3 hubs each, 112 P3 + <=40 new columns <=2pages/3details",
        "oa_deferred": True, "downloads": 0, "formal_admission": False})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    def reject(*_):
        raise RuntimeError("B7_APPLICATION_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject)
    class Fetch(audit.AuditFetch):
        async def get(self, url, *pos, **kw):
            if urlsplit(url).hostname == "oa.jlu.edu.cn":
                raise SourceError("OA_DEFERRED_ZERO_REQUESTS")
            return await super().get(url, *pos, **kw)
    fetch = Fetch()
    try:
        if args.stage in {"discovery", "all"}:
            await discovery(fetch, out)
        if args.stage in {"validation", "all"}:
            targets = validation_targets(out)
            audit.save_json(out / "validation-targets.json", targets)
            previous = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
            results = []
            for target in sorted(targets, key=lambda t: t["old_status"] != "失败"):
                row = previous.get(target["id"]) or await validate(fetch, target, out)
                results.append(row)
                audit.save_json(out / "results.json", results)
                print("COLUMN", len(results), target["institution"], target["column"], row["verdict"], flush=True)
            details = [d for r in results for d in r["details"]]
            audit.save_json(out / "summary.json", {"time": audit.now(), "entries": len(results), "verdicts": dict(Counter(r["verdict"] for r in results)),
                "details": len(details), "verified_details": sum(d["verified"] for d in details), "list_pages": sum(len(r["pages"]) for r in results),
                "list_items": sum(r.get("list_count", 0) for r in results), "isolated_replays": sum(r.get("database_replay", {}).get("passed", False) for r in results),
                "http_attempts_process": fetch.request_count, "cached_requests": len(fetch.cache), "application_db_connections": 0, "oa_requests": 0,
                "cloud_production_verified": False, "complete_downloads": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
