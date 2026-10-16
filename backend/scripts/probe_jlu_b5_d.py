"""Serial, resumable B5-D prefixes; historical restrictions are never retried."""
import argparse
import asyncio
from collections import Counter
import hashlib
import os

import audit_jlu_sites as audit
from probe_jlu_b3 import PrefixAudit
from app.config import get_settings
from app.parsers import parse_detail_html
from app.schemas.notice import NoticeCandidate
from validate_jlu_b5_c import inspect_detail


class B5DFetch(PrefixAudit):
    def __init__(self):
        self.headers_by_url = {}
        super().__init__()

    async def after(self, response):
        self.headers_by_url[str(response.url)] = {k: response.headers[k] for k in ["content-type", "content-range", "content-length", "content-disposition"] if k in response.headers}
        await super().after(response)

    async def probe(self, url, kind):
        result = await super().probe(url, kind)
        headers = self.headers_by_url.get(result.get("final_url", url))
        if headers:
            result["response_headers"] = headers
            audit.save_json(audit.EVIDENCE / "requests.json", self.cache)
        return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = (audit.ROOT / "docs/jlu-fix-b5-d").resolve()
    out = (audit.ROOT / args.output_dir).resolve()
    assert out.is_relative_to(root) and out != root
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    files = ["backend/scripts/probe_jlu_b5_d.py", "backend/scripts/probe_jlu_b3.py", "backend/scripts/audit_jlu_sites.py",
             "backend/scripts/validate_jlu_b5_c.py", "backend/app/services/attachment_validation.py", "backend/app/parsers/html.py",
             "backend/app/services/source_security.py", "backend/app/services/tls.py", "backend/config/sources.yaml",
             "docs/jlu-fix-b5-d/probe-plan.json", "docs/jlu-fix-b5-d/prior-probes.json"]
    hashes = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    previous = audit.load_json(out / "code-manifest.json", {})
    if previous and previous["files"] != hashes:
        raise RuntimeError("Input/code changed; choose a new run directory")
    audit.save_json(out / "code-manifest.json", {"time": previous.get("time", audit.now()), "files": hashes,
                    "limits": "single serial process; shared robots/rate guards; one prefix/column <=4096 bytes; <=2 extra detail previews; max2 transient attempts",
                    "auth_attempts": 0, "oa_requests": 0, "formal_database_access": False})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    connections = []
    def reject(*args):
        connections.append(audit.now())
        raise RuntimeError("B5_D_APPLICATION_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject)
    settings = get_settings()
    audit.save_json(out / "environment-availability.json", {"time": audit.now(), "current_process_role": settings.effective_deployment_role,
         "public_feed_url_configured": bool(settings.public_feed_url), "cloud_admin_url_configured": bool(settings.cloud_admin_url),
         "actual_linux_cloud_crawl": "NOT_VERIFIED_NO_APPROVED_RUNTIME", "actual_cloud_feed": "NOT_CONFIGURED" if not settings.public_feed_url else "NOT_VERIFIED",
         "desktop_execution": "prior installed-client cache + isolated controlled regression; not a fresh installed-client crawl",
         "system_network_modified": False})
    plan = audit.load_json(root / "probe-plan.json", [])
    prior = audit.load_json(root / "prior-probes.json", {})["unique_endpoints"]
    old = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    rows = []
    fetch = B5DFetch()
    try:
        for target in plan:
            row = old.get(target["id"])
            if row is None:
                row = {"id": target["id"], "url": target["url"], "column": target["column"], "recorded_at": audit.now(),
                       "enabled": False, "extra_details": [], "attachment_probe": None, "selected_attachment": target["selected_attachment"],
                       "complete_download_verified": False, "actual_cloud_verified": False}
                if target["deferred"]:
                    row.update(verdict="DEFERRED_OA_AT_USER_REQUEST", reason="Keep prior access-blocked evidence; no OA network or UI/status repair")
                else:
                    attachment = target["selected_attachment"]
                    for item in target["extra_details"]:
                        response = await fetch.get(item["url"])
                        detail = {"url": item["url"], "response": {k: v for k, v in response.items() if k != "html"}}
                        if response.get("ok") and not response.get("auth"):
                            try:
                                parsed = parse_detail_html(response["html"], response["final_url"], NoticeCandidate.model_validate(item))
                                comparison = inspect_detail(response["html"], response["final_url"], parsed)
                                detail.update(comparison=comparison, attachments=[a.model_dump() for a in parsed.attachments])
                                if parsed.attachments and attachment is None:
                                    attachment = {**parsed.attachments[0].model_dump(), "article_url": item["url"], "article_captured_at": response["time"]}
                            except ValueError as exc:
                                detail["error"] = str(exc)
                        row["extra_details"].append(detail)
                    row["selected_attachment"] = attachment
                    if attachment:
                        if attachment["url"] in prior:
                            history = prior[attachment["url"]]
                            probe = {**history["probe"], "mode": "HISTORICAL_REUSE_NO_HTTP", "prefix_evidence": history["prefix_evidence"], "evidence_stage": history["stage"]}
                        else:
                            probe = {**await fetch.probe(attachment["url"], attachment["type"]), "mode": "LIVE_BOUNDED_PREFIX"}
                        row["attachment_probe"] = probe
                        row.update(verdict="PREFIX_EVIDENCE_ONLY" if probe.get("file_prefix_verified") else "ATTACHMENT_CAPABILITY_LIMITED", reason=probe["reason"])
                    else:
                        row.update(verdict="NO_ATTACHMENT_IN_BOUNDED_SAMPLE", reason="No file in existing three plus at most two extra article previews; not proof of all historical articles having no attachments")
            rows.append(row)
            audit.save_json(out / "results.json", rows)
            print(row["id"], row["verdict"], (row["attachment_probe"] or {}).get("category"), flush=True)
        assert not connections
        selected = {r["attachment_probe"]["url"]: r["attachment_probe"] for r in rows if r["attachment_probe"]}
        fresh = {u: p for u, p in selected.items() if p["mode"] == "LIVE_BOUNDED_PREFIX"}
        summary = {"time": audit.now(), "columns": len(rows), "verdicts": dict(Counter(r["verdict"] for r in rows)),
                   "selected_unique_endpoints": len(selected), "selected_categories": dict(Counter(p["category"] for p in selected.values())),
                   "fresh_unique_endpoints": len(fresh), "fresh_categories": dict(Counter(p["category"] for p in fresh.values())),
                   "historical_selected_endpoints_reused": len(selected) - len(fresh), "extra_detail_previews": sum(len(r["extra_details"]) for r in rows),
                   "http_attempts_this_session": fetch.request_count, "app_database_connections": len(connections), "oa_network_requests": 0,
                   "complete_downloads": 0, "formal_admissions": 0, "formal_sources_changed": 0, "cloud_production_verified": False}
        audit.save_json(out / "summary.json", summary)
        print(summary, flush=True)
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
