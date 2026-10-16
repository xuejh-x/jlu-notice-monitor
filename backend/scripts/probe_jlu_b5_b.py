"""Serial, resumable date-evidence review of six disabled YZB columns."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import os
import shutil
from urllib.parse import urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.services.normalization import normalize_whitespace
from app.sources.base import SourceError
from app.sources.generic import GenericPublicSource
from jlu_date_evidence import assess_dates
from validate_jlu_b4 import inspect_sample


def compact(record):
    return {key: value for key, value in record.items() if key != "html"}


def list_evidence(html, page_url, item):
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.select("a[href]"):
        if urljoin(page_url, anchor["href"]) != item.url:
            continue
        row = anchor.find_parent(["li", "tr"]) or anchor.parent
        return {"row_text": normalize_whitespace(row.get_text(" ", strip=True)),
                "date_nodes": [{"text": normalize_whitespace(n.get_text(" ", strip=True)),
                                "datetime": n.get("datetime")} for n in row.select("time,.time,.date,.date1,.date-box")],
                "title_attribute": anchor.get("title"),
                "explicit_publication_label": "发布日期" in row.get_text() or "发布时间" in row.get_text()}
    return {"reason": "LIST_ROW_NOT_FOUND"}


async def review(fetch, candidate):
    config = candidate["config"]
    assert config["enabled"] is False and config["auth_type"] == "none" and not config["allow_private_network"]
    assert config["parser_config"].get("pagination_limit", 1) == 1
    url = config["base_url"]
    listing = await fetch.get(url)
    result = {"id": candidate["id"], "institution": candidate["institution"], "column": candidate["column"],
              "url": url, "checked_at": audit.now(), "response": compact(listing), "details": [],
              "enabled": False, "status": "失败", "verdict": "ACCESS_OR_PARSER_BLOCKED",
              "cloud_production_verified": False, "pagination_verified": False, "attachment_downloads": 0}
    if not listing.get("ok") or listing.get("auth"):
        result["reason"] = listing.get("error", "AUTH_REQUIRED")
        return result
    source = GenericPublicSource(config)
    original = source.fetcher

    class PreviewFetcher:
        async def get(self, target):
            if urlsplit(target).hostname != urlsplit(url).hostname:
                raise SourceError("B5_B_CROSS_HOST_NOT_FETCHED")
            value = await fetch.get(target)
            if not value.get("ok") or value.get("auth"):
                raise SourceError(value.get("error", "AUTH_REQUIRED"))
            if urlsplit(value["final_url"]).hostname != urlsplit(url).hostname:
                raise SourceError("B5_B_CROSS_HOST_REDIRECT_NOT_ADMITTED")
            return value["html"], value["content_type"], value["final_url"]

        async def validate_url(self, target):
            return await fetch.fetcher.validate_url(target)

        async def close(self):
            pass

    source.fetcher = PreviewFetcher()
    try:
        items = await source.fetch_list()
        result["list_count"] = len(items)
        result["list_items"] = [i.model_dump(mode="json") for i in items]
        internal = [i for i in items if urlsplit(i.url).hostname == urlsplit(url).hostname]
        result["external_references_not_fetched"] = [i.url for i in items if i not in internal]
        selected = []
        for strategy, item in [("first_row_possible_pin", internal[0] if internal else None),
                               ("second_row", internal[1] if len(internal) > 1 else None),
                               ("oldest_dated_row_on_first_screen", min((i for i in internal if i.publish_date), key=lambda i: i.publish_date, default=None))]:
            if item and not any(i.url == item.url for _, i in selected):
                selected.append((strategy, item))
        for item in internal:
            if len(selected) >= 3:
                break
            if not any(i.url == item.url for _, i in selected):
                selected.append(("remaining_first_screen_row", item))
        for strategy, item in selected:
            detail = {"url": item.url, "selection": strategy, "list_date": str(item.publish_date or ""),
                      "list_dom": list_evidence(listing["html"], listing["final_url"], item)}
            try:
                parsed = await source.fetch_detail(item)
                record = fetch.inflate(fetch.cache[audit.request_url(item.url)])
                comparison = inspect_sample(record["html"], record["final_url"], parsed)
                dates = assess_dates(record["html"], list_date=item.publish_date, parsed_date=parsed.publish_date)
                detail.update(response=compact(record), title=parsed.title, date=str(parsed.publish_date or ""),
                              content_chars=len(parsed.content), content_sha256=hashlib.sha256(parsed.content.encode()).hexdigest(),
                              attachments=[a.model_dump() for a in parsed.attachments], comparison=comparison, date_evidence=dates,
                              structural_verified=all(comparison[k + "_verified"] for k in ["title", "body", "attachments"]))
            except (SourceError, ValueError) as exc:
                detail.update(reason=str(exc), structural_verified=False,
                              response=compact(fetch.cache.get(audit.request_url(item.url), {})))
            result["details"].append(detail)
        result["needed_details"] = min(3, len(internal))
        structural = bool(selected) and all(d.get("structural_verified") for d in result["details"])
        confirmed = bool(selected) and all(d.get("date_evidence", {}).get("publication_verified") for d in result["details"])
        result["publication_verified_details"] = sum(d.get("date_evidence", {}).get("publication_verified", False) for d in result["details"])
        if structural:
            result.update(status="部分通过", verdict="DATE_SAMPLE_CONFIRMED_PENDING_OTHER_GATES" if confirmed else "DATE_SEMANTICS_UNCONFIRMED_DISABLED",
                          reason="Explicit publication evidence verified; pagination, environment and downloads remain unverified" if confirmed else
                          "Bare list dates and detail update timestamps do not establish publication semantics; candidate remains disabled")
        else:
            result["reason"] = "Title/body/attachment DOM comparison or bounded detail preview did not verify"
        return result
    except (SourceError, ValueError) as exc:
        result["reason"] = str(exc)
        return result
    finally:
        await original.close()
        await source.close()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--review-input-dir", help="Replay exact saved HTML with original capture times; no HTTP fallback")
    args = parser.parse_args()
    out = (audit.ROOT / args.output_dir).resolve()
    root = (audit.ROOT / "docs/jlu-fix-b5-b").resolve()
    assert out.is_relative_to(root) and out != root
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    files = ["backend/scripts/probe_jlu_b5_b.py", "backend/scripts/jlu_date_evidence.py",
             "backend/scripts/audit_jlu_sites.py", "backend/scripts/validate_jlu_b4.py",
             "backend/app/parsers/html.py", "backend/app/sources/generic.py", "backend/app/sources/base.py",
             "backend/app/services/source_security.py", "backend/app/services/tls.py", "backend/app/services/dates.py",
             "backend/config/sources.yaml", "backend/config/settings.yaml", "docs/jlu-fix-b4/source-candidates.json"]
    hashes = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    input_dir = None
    if args.review_input_dir:
        input_dir = (audit.ROOT / args.review_input_dir).resolve()
        assert input_dir.is_relative_to(root) and input_dir != out
        for name in ["requests.json", "code-manifest.json"]:
            hashes["review-input/" + name] = hashlib.sha256((input_dir / name).read_bytes()).hexdigest()
    previous = audit.load_json(out / "code-manifest.json", {})
    if previous and previous.get("files") != hashes:
        raise RuntimeError("Code/input fingerprint changed; choose a new directory")
    audit.save_json(out / "code-manifest.json", {"time": previous.get("time", audit.now()), "files": hashes,
                    "mode": "offline replay of saved live HTML; no HTTP" if input_dir else "live serial read-only local; cached exact URLs on resume", "database": "sqlite://",
                    "review_input_dir": args.review_input_dir,
                    "limits": "one page, three details/column, global 1s/origin 1.2s, transient max 2 attempts",
                    "cloud_production_verified": False, "login_attempts": 0})
    # Importing the source registry creates an engine; prohibit actual connections.
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    connections = []
    def reject_connection(*args):
        connections.append(audit.now())
        raise RuntimeError("B5_B_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject_connection)
    candidates = [c for c in audit.load_json(audit.ROOT / "docs/jlu-fix-b4/source-candidates.json", []) if c["id"].startswith("yzb-")]
    assert len(candidates) == 6
    old = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    results = []
    class OfflineFetch(audit.AuditFetch):
        def __init__(self):
            super().__init__()
            self.cache = audit.load_json(input_dir / "requests.json", {})
            for record in self.cache.values():
                if not record.get("html_path"):
                    continue
                source_path = input_dir / record["html_path"]
                assert hashlib.sha256(source_path.read_bytes()).hexdigest() == record["sha256"]
                destination = out / record["html_path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination)
            audit.save_json(out / "requests.json", self.cache)

        async def get(self, target):
            key = audit.request_url(target)
            if key not in self.cache:
                raise SourceError("OFFLINE_URL_NOT_CAPTURED: " + key)
            return self.inflate(self.cache[key])

    fetch = OfflineFetch() if input_dir else audit.AuditFetch()
    try:
        for candidate in candidates:
            row = old.get(candidate["id"])
            if row is None:
                row = await review(fetch, candidate)
            results.append(row)
            audit.save_json(out / "results.json", results + [v for k, v in old.items() if k not in {r["id"] for r in results}])
            print(candidate["id"], row["verdict"], flush=True)
        assert not connections
        if input_dir:
            assert fetch.request_count == 0 and not fetch.responses
        details = [d for r in results for d in r["details"]]
        summary = {"time": audit.now(), "columns": len(results), "statuses": dict(Counter(r["status"] for r in results)),
                   "verdicts": dict(Counter(r["verdict"] for r in results)), "detail_previews": len(details),
                   "unique_detail_urls": len({d["url"] for d in details}),
                   "structurally_verified_details": sum(d.get("structural_verified", False) for d in details),
                   "publication_verified_details": sum(d.get("date_evidence", {}).get("publication_verified", False) for d in details),
                   "date_verdicts": dict(Counter(d.get("date_evidence", {}).get("verdict", "NOT_CHECKED") for d in details)),
                   "list_matches_update": sum(d.get("date_evidence", {}).get("list_matches_update", False) for d in details),
                   "http_attempts_this_session": fetch.request_count, "cached_exact_urls": len(fetch.cache),
                   "database_url": str(engine.url), "database_connection_attempts": len(connections),
                   "formal_sources_changed": 0, "candidates_enabled": 0, "attachment_downloads": 0,
                   "cloud_production_verified": False, "pagination_verified": False,
                   "mode": "offline replay" if input_dir else "live", "review_input_dir": args.review_input_dir}
        audit.save_json(out / "summary.json", summary)
        print(summary, flush=True)
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
