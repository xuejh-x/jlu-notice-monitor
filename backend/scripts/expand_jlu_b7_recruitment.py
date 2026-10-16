"""Rescan captured home/hub pages for the proven missing recruitment label."""
import asyncio
import csv
import hashlib
import os
import shutil
from urllib.parse import urlsplit

import audit_jlu_sites as audit
import validate_jlu_b6 as core
import review_jlu_b7 as review
from run_jlu_b7 import links

ROOT = audit.ROOT / "docs/jlu-fix-b7"
INPUT = ROOT / "followup-3-20261015"
OUT = ROOT / "recruitment-20261015"


async def main():
    audit.EVIDENCE = OUT
    os.environ["JLU_APP_DATA_DIR"] = str(OUT / "runtime")
    cache = audit.load_json(INPUT / "requests.json", {})
    names = ["backend/scripts/expand_jlu_b7_recruitment.py", "backend/scripts/audit_jlu_sites.py", "backend/scripts/review_jlu_b7.py", "backend/scripts/validate_jlu_b6.py",
             "backend/app/parsers/html.py", "backend/app/sources/generic.py", "backend/app/services/deduplication.py", "backend/app/services/list_pagination.py",
             "backend/app/services/source_security.py", "backend/app/services/tls.py", "backend/config/sources.yaml"]
    hashes = {n: hashlib.sha256((audit.ROOT / n).read_bytes()).hexdigest() for n in names}
    hashes["input/requests.json"] = hashlib.sha256((INPUT / "requests.json").read_bytes()).hexdigest()
    assert not (OUT / "summary.json").exists()
    audit.save_json(OUT / "code-manifest.json", {"time": audit.now(), "files": hashes, "input_dir": str(INPUT.relative_to(audit.ROOT)),
        "limits": "rescan cached 59 home/hub records + 2 new official sites only; <=8 new literal recruitment columns; <=2pages/3details; serial robots/rates"})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    def reject(*_):
        raise RuntimeError("B7_RECRUITMENT_DATABASE_FORBIDDEN")
    event.listen(engine, "connect", reject)
    fetch = audit.AuditFetch()
    for key, r in cache.items():
        if r.get("html_path"):
            source = INPUT / r["html_path"]
            assert hashlib.sha256(source.read_bytes()).hexdigest() == r["sha256"]
            dest = OUT / r["html_path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        fetch.cache[key] = r
    audit.save_json(OUT / "requests.json", fetch.cache)
    records = []
    for s in audit.load_json(ROOT / "live-20261015/site-results.json", []):
        for r in [s.get("response"), *s["pages"]]:
            if r and r.get("ok") and r.get("html_path"):
                records.append((s["institutions"], s["site_url"], r))
    for s in audit.load_json(ROOT / "supplement-20261015/official-supplement.json", []):
        if s["kind"] == "site_identity":
            for r in [s["response"], s.get("home_response")]:
                if r and r.get("ok") and r.get("html_path"):
                    records.append(([s["institution"]], (s.get("home_response") or s["response"]).get("final_url"), r))
    known = {audit.norm(r["column_url"]) for r in csv.DictReader((audit.ROOT / "docs/jlu-compatibility-report.csv").open(encoding="utf-8-sig"))}
    discovered = {}
    for institutions, site, r in records:
        html = (INPUT / r["html_path"]).read_bytes().decode("utf-8")
        anchors = links(html, r["final_url"])
        for u, label in audit.column_links(html, r["final_url"]).items():
            if "人才招聘" not in label or u in known:
                continue
            exact = next((a["url"] for a in anchors if audit.norm(a["url"]) == u), None)
            if exact is None or urlsplit(exact).hostname != urlsplit(r["final_url"]).hostname:
                continue
            key = hashlib.sha256(exact.encode()).hexdigest()[:12]
            discovered.setdefault(u, {"id": "recruitment-" + key, "url": exact, "institution": " / ".join(institutions), "column": label,
                "site_url": site, "priority": "P3", "discovery_url": r["final_url"], "discovery_snapshot": r["html_path"], "capture_time": r["time"],
                "old_status": "新发现未验证", "old_issues": "DISCOVERY_LABEL_MISSED", "original_evidence": "",
                "config": {"code": "candidate-jlu-b7-" + key, "name": " / ".join(institutions) + " / " + label, "base_url": exact,
                    "parser": "generic_html", "enabled": False, "auth_type": "none", "allow_private_network": False, "validation_scope": "local",
                    "execution_policy": "cloud_preferred", "parser_config": {"pagination_limit": 2}}})
    selected = list(discovered.values())[:8]
    audit.save_json(OUT / "discovered-columns.json", list(discovered.values()))
    audit.save_json(OUT / "columns-not-selected.json", list(discovered.values())[8:])
    targets = audit.load_json(INPUT / "validation-targets.json", []) + selected
    audit.save_json(OUT / "validation-targets.json", targets)
    rows = audit.load_json(ROOT / "review-accepted-20261015/results.json", [])
    core.compare, core.independent_urls = review.compare, review.independent_urls
    try:
        for target in selected:
            rows.append(await core.validate(fetch, target, OUT))
            audit.save_json(OUT / "results.json", rows)
            print(target["url"], rows[-1]["verdict"], flush=True)
        audit.save_json(OUT / "results.json", rows)
        audit.save_json(OUT / "summary.json", {"time": audit.now(), "new_discovered_columns": len(discovered), "new_checked_columns": len(selected),
            "entries": len(rows), "http_attempts_process": fetch.request_count, "application_db_connections": 0, "downloads": 0, "oa_requests": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
