"""Bounded, serial B5-A public access diagnosis; no crawler, DB or login."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
import os
from urllib.parse import urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.parsers.html import validate_html_page
from app.services.normalization import normalize_whitespace
from app.sources.oa_public import parse_oa_list_html, parse_oa_detail_html, parse_oa_attachment_references


def category(record):
    if not record.get("ok"):
        error = record.get("error", "")
        for marker, label in [("ROBOTS_DISALLOWED", "ROBOTS_DISALLOWED"),
                              ("CERTIFICATE_VERIFY_FAILED", "TLS_CERTIFICATE_VERIFY_FAILED"),
                              ("SSLEOFError", "TLS_EOF"), ("Timeout", "TIMEOUT"),
                              ("redirect limit", "REDIRECT_LIMIT"), ("HTTP_403", "HTTP_403")]:
            if marker in error:
                return label
        return "ROBOTS_UNAVAILABLE" if "ROBOTS_UNAVAILABLE" in error else "ACCESS_FAILED"
    try:
        validate_html_page(BeautifulSoup(record["html"], "html.parser"))
    except ValueError as exc:
        return "PERMISSION_RESTRICTED" if "PERMISSION" in str(exc) else "AUTH_OR_ERROR_PAGE"
    return "HTTP_CONTENT_AVAILABLE_NOT_ADMITTED"


def compact(record):
    return {key: value for key, value in record.items() if key != "html"}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reuse-input-dir", help="Reuse saved requests with original times; fetch only uncached exact URLs")
    args = parser.parse_args()
    root = audit.ROOT / "docs/jlu-fix-b5-a"
    out = (audit.ROOT / args.output_dir).resolve()
    assert out.is_relative_to(root.resolve()) and out != root.resolve()
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    files = ["backend/app/sources/generic.py", "backend/app/sources/base.py", "backend/app/parsers/html.py",
             "backend/app/services/http_diagnostics.py", "backend/app/services/tls.py", "backend/app/services/source_security.py",
             "backend/app/sources/oa_public.py", "backend/scripts/audit_jlu_sites.py", "backend/scripts/probe_jlu_b5_a.py",
             "backend/config/sources.yaml", "docs/jlu-fix-b4/source-candidates.json"]
    hashes = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    if args.reuse_input_dir:
        previous_dir = (audit.ROOT / args.reuse_input_dir).resolve()
        assert previous_dir.is_relative_to(root.resolve()) and previous_dir != out
        for filename in ["requests.json", "code-manifest.json"]:
            hashes["reuse-input/" + filename] = hashlib.sha256((previous_dir / filename).read_bytes()).hexdigest()
    previous = audit.load_json(out / "code-manifest.json", {})
    if previous and previous.get("files") != hashes:
        raise RuntimeError("Code/input fingerprint changed; choose a new directory")
    audit.save_json(out / "code-manifest.json", {"time": audit.now(), "files": hashes,
        "mode": "mixed saved requests + uncached live URLs" if args.reuse_input_dir else "live serial read-only default local network path",
        "reuse_input_dir": args.reuse_input_dir, "database": "sqlite://",
        "auth": "none", "network_changes": False, "cloud_production_verified": False})
    candidates = {c["id"]: c for c in audit.load_json(audit.ROOT / "docs/jlu-fix-b4/source-candidates.json", [])}
    source = next(c for c in audit.load_yaml("sources.yaml")["sources"] if c["code"] == "oa")
    cases = [("oa", source["sections"][0]["url"]),
             *[(key, candidates[key]["config"]["base_url"]) for key in ["defense-conditional", "continuing-conditional",
               "continuing-academic-conditional", "jwc-teaching-publicity"]],
             ("sports-oa-index", "http://isc.jlu.edu.cn/oaindex.htm"),
             ("sports-login-reference", "https://oa.jlu.edu.cn/defaultroot/login.jsp")]
    homes = [source["base_url"].rstrip("/") + "/", "https://dec.jlu.edu.cn/", "https://jwc.jlu.edu.cn/", "http://isc.jlu.edu.cn/"]
    fetch = audit.AuditFetch()
    if args.reuse_input_dir and not fetch.cache:
        for url, record in audit.load_json(previous_dir / "requests.json", {}).items():
            if record.get("html_path"):
                raw = (previous_dir / record["html_path"]).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == record["sha256"]
                path = out / record["html_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            fetch.cache[url] = record
        audit.save_json(out / "requests.json", fetch.cache)
    # app.sources imports its registry/Cloud module eagerly, which creates an
    # in-memory engine. Forbid any actual connection during this public probe.
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    db_attempts = []
    def reject_db_connection(*args):
        db_attempts.append(audit.now())
        raise RuntimeError("B5_A_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject_db_connection)
    observations = []
    try:
        for url in homes:
            record = await fetch.get(url)
            entry = {"url": url, "captured_at": record["time"], "category": category(record), "response": compact(record), "links": []}
            if record.get("ok"):
                soup = BeautifulSoup(record["html"], "html.parser")
                seen = set()
                for a in soup.select("a[href]"):
                    label = normalize_whitespace(a.get_text(" ", strip=True))
                    target = urljoin(record["final_url"], a["href"])
                    exact_column = target.rstrip("/") in {case_url for _, case_url in cases}
                    if (audit.NOTICE.search(label) or label in {"校内通知", "教学公示"} or exact_column) and target not in seen:
                        if urlsplit(target).scheme not in {"http", "https"}:
                            continue
                        seen.add(target)
                        entry["links"].append({"title": label, "url": target})
                        if len(entry["links"]) == 12:
                            break
            observations.append(entry)
            audit.save_json(out / "home-observations.json", observations)
        results = []
        for key, url in cases:
            print(key, url, flush=True)
            if key == "sports-login-reference":
                results.append({"id": key, "url": url, "category": "LOGIN_REFERENCE_NOT_FETCHED",
                                "captured_at": None, "recorded_at": audit.now(), "reason": "Known login reference; no login request or notice admission", "details": []})
                continue
            record = await fetch.get(url)
            row = {"id": key, "url": url, "captured_at": record["time"], "category": category(record),
                   "response": compact(record), "details": [], "formal_admission": False, "cloud_production_verified": False}
            if key == "oa" and row["category"] == "HTTP_CONTENT_AVAILABLE_NOT_ADMITTED":
                items = parse_oa_list_html(record["html"], record["final_url"])
                row["list_count"] = len(items)
                row["list_items"] = [item.model_dump(mode="json") for item in items]
                for item in items[:2]:
                    detail = await fetch.get(item.url)
                    d = {"url": item.url, "response": compact(detail), "category": category(detail)}
                    if d["category"] == "HTTP_CONTENT_AVAILABLE_NOT_ADMITTED":
                        parsed = parse_oa_detail_html(detail["html"], detail["final_url"], item)
                        soup = BeautifulSoup(detail["html"], "html.parser")
                        heading = soup.select_one(".content_t")
                        body = soup.select_one(".content_font.fontsize, .content_font")
                        if body:
                            for unwanted in list(body.select("script,style,noscript")):
                                unwanted.decompose()
                        d.update(title=parsed.title, date=str(parsed.publish_date), content_chars=len(parsed.content),
                            title_verified=bool(heading and normalize_whitespace(heading.get_text(" ", strip=True)) == parsed.title),
                            body_verified=bool(body and normalize_whitespace(body.get_text("\n", strip=True)) == parsed.content),
                            content_sha256=hashlib.sha256(parsed.content.encode()).hexdigest(),
                            attachment_references=len(parse_oa_attachment_references(detail["html"], item.url)),
                            encoder_post_exercised=False)
                    row["details"].append(d)
            results.append(row)
            audit.save_json(out / "results.json", results)
            print(row["category"], flush=True)
        # Follow only links actually observed on the official home; no URL guessing.
        alternatives = []
        for home in observations:
            if urlsplit(home["url"]).hostname not in {"dec.jlu.edu.cn", "jwc.jlu.edu.cn"}:
                continue
            selected = [link for link in home["links"] if urlsplit(link["url"]).hostname == urlsplit(home["url"]).hostname
                        and (link["url"].rstrip("/") in {url for _, url in cases} if "dec." in home["url"] else "教学公示" in link["title"])]
            for link in selected[:2]:
                if link["url"] in {url for _, url in cases}:
                    continue
                response = await fetch.get(link["url"])
                alternatives.append({"discovery_url": home["url"], **link, "category": category(response),
                                     "response": compact(response), "enabled": False, "support_status": "NOT_ADMITTED"})
        results.append({"id": "quantity-old-link", "url": "http://jlucqe.jlu.edu.cn/list.php?SID=1",
                        "category": "DEFERRED_TO_B7_NOT_FETCHED", "captured_at": None, "recorded_at": audit.now(),
                        "reason": "Original 404 only; planned B7 official-entry review", "details": []})
        audit.save_json(out / "results.json", results)
        audit.save_json(out / "alternatives.json", alternatives)
        summary = {"time": audit.now(), "cases": len(results), "categories": dict(Counter(r["category"] for r in results)),
            "home_pages_attempted": len(homes), "observed_alternatives_attempted": len(alternatives),
            "http_attempts": fetch.request_count, "http_responses_this_session": len(fetch.responses),
            "details_attempted": sum(len(r["details"]) for r in results), "formal_sources_changed": 0,
            "complete_downloads": 0, "database_imported": any(name.startswith("app.database") for name in __import__("sys").modules),
            "database_url": str(engine.url), "database_connection_attempts": len(db_attempts),
            "mode": "mixed saved requests + uncached live URLs" if args.reuse_input_dir else "live",
            "reuse_input_dir": args.reuse_input_dir}
        assert not db_attempts
        audit.save_json(out / "summary.json", summary)
        print(summary, flush=True)
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
