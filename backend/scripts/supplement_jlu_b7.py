"""Fetch only primary official search evidence and explicit new notice links."""
import asyncio
from collections import Counter
import hashlib
import os
import shutil
from urllib.parse import urlsplit

import audit_jlu_sites as audit
from app.sources.base import SourceError
from run_jlu_b7 import links
from validate_jlu_b6 import compact, validate

ROOT = audit.ROOT / "docs/jlu-fix-b7"
INPUT = ROOT / "live-20261015"
OUT = ROOT / "supplement-20261015"


async def main():
    assert (INPUT / "summary.json").exists(), "Do not overlap network batches"
    audit.EVIDENCE = OUT
    os.environ["JLU_APP_DATA_DIR"] = str(OUT / "runtime")
    names = ["backend/scripts/supplement_jlu_b7.py", "backend/scripts/run_jlu_b7.py", "backend/scripts/validate_jlu_b6.py",
             "backend/scripts/audit_jlu_sites.py", "backend/app/parsers/html.py", "backend/app/sources/generic.py",
             "backend/app/services/deduplication.py", "backend/app/services/source_security.py", "backend/app/services/tls.py",
             "backend/config/sources.yaml", "docs/jlu-fix-b7/search-supplement.json"]
    hashes = {n: hashlib.sha256((audit.ROOT / n).read_bytes()).hexdigest() for n in names}
    hashes["input/requests.json"] = hashlib.sha256((INPUT / "requests.json").read_bytes()).hexdigest()
    old = audit.load_json(OUT / "code-manifest.json", {})
    assert not old or old["files"] == hashes
    audit.save_json(OUT / "code-manifest.json", {"time": old.get("time", audit.now()), "files": hashes,
        "limits": "7 primary evidence URLs, <=2 literal same-site home links, <=8 new columns, <=2 pages/3 samples; shared serial audit limiter/robots",
        "input_dir": str(INPUT.relative_to(audit.ROOT)), "database": "sqlite://; application connections forbidden", "downloads": 0})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    def reject(*_):
        raise RuntimeError("B7_SUPPLEMENT_DATABASE_FORBIDDEN")
    event.listen(engine, "connect", reject)
    class Fetch(audit.AuditFetch):
        async def get(self, url, *pos, **kw):
            if urlsplit(url).hostname == "oa.jlu.edu.cn":
                raise SourceError("OA_DEFERRED_ZERO_REQUESTS")
            return await super().get(url, *pos, **kw)
    fetch = Fetch()
    if not fetch.cache:
        for key, value in audit.load_json(INPUT / "requests.json", {}).items():
            if value.get("html_path"):
                path = INPUT / value["html_path"]
                assert hashlib.sha256(path.read_bytes()).hexdigest() == value["sha256"]
                dest = OUT / value["html_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
            fetch.cache[key] = value
        audit.save_json(OUT / "requests.json", fetch.cache)
    seeds = audit.load_json(ROOT / "search-supplement.json", {})["seeds"]
    targets = audit.load_json(INPUT / "validation-targets.json", [])
    known = {audit.norm(t["url"]) for t in targets}
    columns = {}
    evidence = []
    try:
        for seed in seeds:
            r = await fetch.get(seed["url"])
            row = {**seed, "response": compact(r), "home_response": None, "column_links": []}
            if r.get("ok") and not r.get("auth") and seed["kind"] == "site_identity":
                row["visible_self_identification"] = seed["institution"].replace("有限责任公司", "") in r["html"]
                pages = [r]
                homepage = next((a["url"] for a in links(r["html"], r["final_url"]) if a["label"] in {"首页", "首 页", "网站首页"}
                    and urlsplit(a["url"]).hostname == urlsplit(r["final_url"]).hostname), None)
                if homepage:
                    h = await fetch.get(homepage)
                    row["home_response"] = compact(h)
                    if h.get("ok") and not h.get("auth"):
                        pages.append(h)
                for page in pages:
                    observed = links(page["html"], page["final_url"])
                    for url, label in audit.column_links(page["html"], page["final_url"]).items():
                        exact = next((a["url"] for a in observed if audit.norm(a["url"]) == url), None)
                        if exact and urlsplit(exact).hostname == urlsplit(page["final_url"]).hostname:
                            c = {"url": exact, "institution": seed["institution"], "column": label, "priority": "P3",
                                 "site_url": (row.get("home_response") or {}).get("final_url") or r["final_url"],
                                 "discovery_url": page["final_url"], "discovery_snapshot": page["html_path"], "capture_time": page["time"]}
                            row["column_links"].append(c)
                            if audit.norm(exact) not in known:
                                columns.setdefault(audit.norm(exact), c)
            evidence.append(row)
            audit.save_json(OUT / "official-supplement.json", evidence)
            print("EVIDENCE", seed["institution"], r.get("ok"), len(row["column_links"]), flush=True)
        for c in list(columns.values())[:8]:
            key = hashlib.sha256(c["url"].encode()).hexdigest()[:12]
            targets.append({**c, "id": "supplement-" + key, "old_status": "新发现未验证", "old_issues": "", "original_evidence": "",
                "config": {"code": "candidate-jlu-b7-" + key, "name": c["institution"] + " / " + c["column"], "base_url": c["url"],
                    "parser": "generic_html", "enabled": False, "auth_type": "none", "allow_private_network": False,
                    "validation_scope": "local", "execution_policy": "cloud_preferred", "parser_config": {"pagination_limit": 2}}})
        audit.save_json(OUT / "columns-not-selected.json", list(columns.values())[8:])
        audit.save_json(OUT / "validation-targets.json", targets)
        rows = audit.load_json(INPUT / "results.json", [])
        for target in targets[len(rows):]:
            rows.append(await validate(fetch, target, OUT))
            audit.save_json(OUT / "results.json", rows)
            print("NEW_COLUMN", target["url"], rows[-1]["verdict"], flush=True)
        audit.save_json(OUT / "results.json", rows)
        audit.save_json(OUT / "summary.json", {"time": audit.now(), "evidence_pages": len(evidence), "new_columns": len(targets) - len(audit.load_json(INPUT / "validation-targets.json", [])),
            "entries": len(rows), "verdicts": dict(Counter(r["verdict"] for r in rows)), "http_attempts_process": fetch.request_count,
            "application_db_connections": 0, "downloads": 0, "oa_requests": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
