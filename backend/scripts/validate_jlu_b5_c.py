"""Bounded serial pagination previews; actual-source replay into isolated memory DB."""
import argparse
import asyncio
from collections import Counter
from contextlib import nullcontext
from dataclasses import asdict
import hashlib
import os
import re
from pathlib import Path
import shutil
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.sources.base import SourceError
from app.sources.registry import build_source
from app.sources.generic import GenericPublicSource
from app.services.normalization import canonicalize_url
from app.parsers.html import CONTENT_SELECTORS
from validate_jlu_b4 import inspect_sample


def compact(record):
    return {k: v for k, v in record.items() if k != "html"}


def independent_links(html, page_url, target):
    soup = BeautifulSoup(html, "html.parser")
    if target["id"].startswith("employment-"):
        nodes = soup.select(".m-list-line_content h3 a[href]")
    else:
        nodes = soup.select("li a[href],tr a[href]")
        nodes = [n for n in nodes if "/info/" in urljoin(page_url, n["href"])]
    return sorted({canonicalize_url(urljoin(page_url, n["href"])) for n in nodes})


def inspect_detail(html, url, parsed):
    comparison = inspect_sample(html, url, parsed)
    soup = BeautifulSoup(html, "html.parser")
    body = next((soup.select_one(s) for s in CONTENT_SELECTORS if soup.select_one(s) is not None), None)
    references = []
    if body:
        for script in body.select("script:not([src])"):
            # Independent DOM check of the observed PDF call's first literal.
            for raw in re.findall(r"showVsbpdfIframe\(\s*['\"]([^'\"]+\.pdf)['\"]", script.get_text()):
                references.append(urljoin(url, raw))
    if references:
        actual = {a.url for a in parsed.attachments}
        comparison["embedded_pdf_reference_urls"] = references
        comparison["embedded_pdf_references_verified"] = set(references) <= actual
        for n in body.select("script,style,noscript"):
            n.decompose()
        if not body.get_text(strip=True) and not body.select("img") and set(references) <= actual:
            comparison.update(body_verified=True, attachments_verified=True,
                              body_kind="EMBEDDED_PDF_ATTACHMENT_REFERENCE_ONLY", body_text_verified=False,
                              attachment_file_verified=False)
            comparison["issues"] = [i for i in comparison["issues"] if i not in {"BODY_NOT_INDEPENDENTLY_VERIFIED", "ATTACHMENTS_NOT_INDEPENDENTLY_VERIFIED"}]
    return comparison


async def database_rounds(details, code, runtime, *, retain_all_samples=False):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.database import Base
    from app.models import Favorite, Notice, NoticeSourceRelation, Source, UserState
    from app.config import Settings
    from app.crawler.runner import CrawlerManager, SourceRunResult
    import app.crawler.runner as runner

    # Expand retention only in this test so observed old samples can exercise
    # identity/state behavior; production retention is unchanged.
    settings = Settings(_env_file=None, database_url="sqlite://", deployment_role="standalone", app_data_dir=str(runtime), retention_days=3650)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    manager = CrawlerManager(runtime)
    parsed = [p for p in details if p is not None]
    class Replay:
        async def fetch_list(self):
            return [p.model_copy(update={"content": "", "attachments": []}) for p in parsed]
        async def fetch_detail(self, item):
            return next(p for p in parsed if p.url == item.url)
        async def close(self):
            pass
    adapter = Replay()
    try:
        retention_guard = patch.object(runner, "notice_is_expired", return_value=False) if retain_all_samples else nullcontext()
        with Session(engine, expire_on_commit=False) as db, patch.object(runner, "get_settings", return_value=settings), patch.object(runner, "build_source", return_value=adapter), retention_guard:
            source = Source(code=code, name=code, base_url="https://test.invalid")
            db.add(source)
            db.commit()
            config = {"code": code, "name": code, "base_url": source.base_url}
            first = SourceRunResult(source=code)
            await manager._execute_source_attempt(db, source, config, True, first, "local")
            rows = db.scalars(select(Notice)).all()
            for state in db.scalars(select(UserState)):
                state.is_read = state.is_favorite = True
                db.add(Favorite(notice_id=state.notice_id))
            db.commit()
            before = [(n.id, n.public_id, n.canonical_url, n.content_hash, n.version, n.source_id, n.status) for n in rows]
            before_relations = [(r.id, r.notice_id, r.source_id, r.origin_item_key) for r in db.scalars(select(NoticeSourceRelation))]
            before_states = [(s.notice_id, s.is_read, s.is_favorite, s.updated_at.isoformat()) for s in db.scalars(select(UserState))]
            second = SourceRunResult(source=code)
            await manager._execute_source_attempt(db, source, config, False, second, "local")
            after = [(n.id, n.public_id, n.canonical_url, n.content_hash, n.version, n.source_id, n.status) for n in db.scalars(select(Notice))]
            after_relations = [(r.id, r.notice_id, r.source_id, r.origin_item_key) for r in db.scalars(select(NoticeSourceRelation))]
            after_states = [(s.notice_id, s.is_read, s.is_favorite, s.updated_at.isoformat()) for s in db.scalars(select(UserState))]
            return {"mode": "offline parsed-sample replay only", "database": "sqlite://", "retention_days_test_only": 3650,
                    "retention_filter_disabled_for_identity_test": retain_all_samples,
                    "sampled_candidates": len(parsed), "first_round": asdict(first), "second_round": asdict(second),
                    "notice_count": len(after), "relation_count": len(after_relations),
                    "ids_content_baseline_preserved": before == after, "relations_preserved": before_relations == after_relations,
                    "states_preserved": before_states == after_states, "favorites_preserved": len(db.scalars(select(Favorite)).all()) == len(rows),
                    "unexpected_merge_requires_review": len(after) != len({canonicalize_url(p.url) for p in parsed}),
                    "passed": bool(parsed) and before == after and before_relations == after_relations and before_states == after_states
                              and second.new_count == second.updated_count == 0}
    finally:
        engine.dispose()


async def validate(fetch, target, out):
    config = {**target["config"], "enabled": False}
    parser_config = {**config.get("parser_config", {}), "pagination_limit": 3}
    parser_config["next_page_selector"] = ".pagination li:last-child a" if target["id"].startswith("employment-") else '.p_pages .p_next a, a.Next:-soup-contains("下页")'
    config["parser_config"] = parser_config
    row = {"id": target["id"], "url": target["url"], "column": target["column"], "kind": target["kind"],
           "checked_at": audit.now(), "enabled": False, "config": config, "status": "失败", "details": [],
           "formal_admission": False, "cloud_production_verified": False, "history_verified": False}
    first = await fetch.get(target["url"])
    row["response"] = compact(first)
    if not first.get("ok") or first.get("auth"):
        row.update(verdict="ACCESS_BLOCKED", reason=first.get("error", "AUTH_REQUIRED"))
        return row
    adapter = build_source(config) if target["kind"] == "existing" else GenericPublicSource(config)
    original = getattr(adapter, "fetcher", None)
    class Preview:
        async def get(self, url):
            response = await fetch.get(url)
            if not response.get("ok") or response.get("auth"):
                raise SourceError(response.get("error", "AUTH_REQUIRED"))
            return response["html"], response["content_type"], response["final_url"]
        async def validate_url(self, url):
            return await fetch.fetcher.validate_url(url)
        async def close(self):
            pass
    preview = Preview()
    if original:
        await original.close()
        adapter.fetcher = preview
    else:
        async def get_html(url):
            return (await preview.get(url))[0]
        async def get_page(url):
            html, _, final = await preview.get(url)
            return html, final
        adapter._get, adapter._get_list_page = get_html, get_page
    try:
        items = await adapter.fetch_list()
        row["items"] = [i.model_dump(mode="json") for i in items]
        row["pagination"] = adapter.pagination_report
        expected, observed_pages = set(), []
        for page in adapter.pagination_report[0]["pages"]:
            record = fetch.inflate(fetch.cache[audit.request_url(page["url"])])
            references = independent_links(record["html"], record["final_url"], target)
            expected.update(references)
            observed_pages.append({"response": compact(record), "reference_urls": references,
                                   "observed_next_urls": audit.page_next(record["html"], record["final_url"])})
        actual = {canonicalize_url(i.url) for i in items}
        missed_next = adapter.pagination_report[0]["stop_reason"] == "NO_NEXT_PAGE" and bool(observed_pages[-1]["observed_next_urls"])
        row.update(pages=observed_pages, list_count=len(items), missing_reference_urls=sorted(expected - actual),
                   unexpected_urls=sorted(actual - expected), observed_next_missed_by_selector=missed_next,
                   pagination_verified=bool(observed_pages) and actual == expected and not missed_next)
        selected = items[:2]
        if len(observed_pages) > 1:
            second_page_urls = set(observed_pages[1]["reference_urls"]) - set(observed_pages[0]["reference_urls"])
            sample = next((i for i in items if canonicalize_url(i.url) in second_page_urls and i not in selected), None)
            if sample:
                selected.append(sample)
        if len(selected) < 3:
            selected.extend(i for i in items if i not in selected and len(selected) < 3)
        parsed_samples = []
        for item in selected:
            detail = {"url": item.url, "list_title": item.title, "list_date": str(item.publish_date or "")}
            try:
                parsed = await adapter.fetch_detail(item)
                record = fetch.inflate(fetch.cache[audit.request_url(item.url)])
                comparison = inspect_detail(record["html"], record["final_url"], parsed)
                detail.update(response=compact(record), parsed=parsed.model_dump(mode="json"), comparison=comparison,
                              verified=all(comparison[k + "_verified"] for k in ["title", "date", "body", "attachments"]))
                parsed_samples.append(parsed)
            except (SourceError, ValueError) as exc:
                detail.update(reason=str(exc), verified=False, response=compact(fetch.cache.get(audit.request_url(item.url), {})))
            row["details"].append(detail)
        row["database_replay"] = await database_rounds(parsed_samples, target["id"], out / "test-runtime" / target["id"])
        if row["pagination_verified"] and all(d["verified"] for d in row["details"]) and row["database_replay"]["passed"] and not row["database_replay"]["unexpected_merge_requires_review"]:
            row.update(status="部分通过", verdict="BOUNDED_PAGINATION_AND_INCREMENTAL_SAMPLE_PASSED",
                       reason="Bounded pages + scoped detail checks + isolated two-round sample replay passed; Cloud, file downloads and full history unverified")
        else:
            row.update(verdict="SAMPLE_OR_IDENTITY_REVIEW_REQUIRED", reason="Inspect list/detail DOM comparisons and isolated database replay; no admission")
    except (SourceError, ValueError) as exc:
        row.update(verdict="PAGINATION_PREVIEW_FAILED", reason=str(exc), pagination=getattr(adapter, "pagination_report", []))
    finally:
        await adapter.close()
    return row


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--input-dir", default="docs/jlu-fix-b5-c/discovery-20261014")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = (audit.ROOT / "docs/jlu-fix-b5-c").resolve()
    out, input_dir = (audit.ROOT / args.output_dir).resolve(), (audit.ROOT / args.input_dir).resolve()
    assert out.is_relative_to(root) and input_dir.is_relative_to(root) and out != input_dir
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    files = ["backend/scripts/validate_jlu_b5_c.py", "backend/scripts/audit_jlu_sites.py", "backend/scripts/validate_jlu_b4.py",
             "backend/app/services/list_pagination.py", "backend/app/services/deduplication.py", "backend/app/crawler/runner.py",
             "backend/app/sources/generic.py", "backend/app/sources/base.py", "backend/config/sources.yaml"]
    hashes = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    for name in ["requests.json", "code-manifest.json", "targets.json"]:
        hashes["input/" + name] = hashlib.sha256((input_dir / name).read_bytes()).hexdigest()
    hashes["mode"] = "offline" if args.offline else "live with saved exact-URL first screens"
    old = audit.load_json(out / "code-manifest.json", {})
    if old and old["files"] != hashes:
        raise RuntimeError("Changed code/input; choose a new output directory")
    audit.save_json(out / "code-manifest.json", {"time": old.get("time", audit.now()), "files": hashes, "mode": hashes["mode"],
                    "input_dir": str(input_dir.relative_to(audit.ROOT)), "limits": "3 pages/column, <=90 items/column, <=3 detail previews/column; serial; max 2 transient attempts"})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    attempts = []
    def reject(*args):
        attempts.append(audit.now())
        raise RuntimeError("B5_C_APPLICATION_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject)
    class Fetch(audit.AuditFetch):
        async def get(self, url, *positional, **kwargs):
            if args.offline and audit.request_url(url) not in self.cache:
                raise SourceError("OFFLINE_URL_NOT_CAPTURED: " + url)
            return await super().get(url, *positional, **kwargs)
    fetch = Fetch()
    if not fetch.cache:
        for key, record in audit.load_json(input_dir / "requests.json", {}).items():
            if record.get("html_path"):
                path = input_dir / record["html_path"]
                assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
                destination = out / record["html_path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
            fetch.cache[key] = record
        audit.save_json(out / "requests.json", fetch.cache)
    planned = audit.load_json(input_dir / "targets.json", [])
    assert len(planned) == 17
    audit.save_json(out / "targets.json", planned)
    previous = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    results = []
    try:
        for target in planned:
            row = previous.get(target["id"])
            if row is None:
                row = await validate(fetch, target, out)
            results.append(row)
            audit.save_json(out / "results.json", results)
            print(target["id"], row["verdict"], row.get("list_count"), flush=True)
        assert not attempts
        if args.offline:
            assert not fetch.request_count
        details = [d for r in results for d in r["details"]]
        summary = {"time": audit.now(), "columns": len(results), "statuses": dict(Counter(r["status"] for r in results)),
                   "verdicts": dict(Counter(r["verdict"] for r in results)), "list_pages": sum(len(r.get("pages", [])) for r in results),
                   "list_items": sum(r.get("list_count", 0) for r in results), "details": len(details), "verified_details": sum(d["verified"] for d in details),
                   "database_sample_replays": sum("database_replay" in r for r in results),
                   "unexpected_merges": [r["id"] for r in results if r.get("database_replay", {}).get("unexpected_merge_requires_review")],
                   "http_attempts_this_session": fetch.request_count, "app_database_connections": len(attempts),
                   "formal_sources_changed": 0, "formal_admissions": 0, "attachment_downloads": 0, "cloud_production_verified": False}
        audit.save_json(out / "summary.json", summary)
        print(summary, flush=True)
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
