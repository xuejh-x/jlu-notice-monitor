"""Replay immutable audit snapshots through a chosen backend, with no network/DB."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/jlu-audit-evidence"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-dir", default=str(ROOT / "backend"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch", choices=["b0-b1", "b2", "b3", "b4"], default="b0-b1")
    args = parser.parse_args()
    backend = Path(args.backend_dir).resolve()
    output = (ROOT / args.output).resolve()
    assert backend.is_relative_to(ROOT / "backend")
    assert output.is_relative_to(ROOT / "docs" / f"jlu-fix-{args.batch}")
    os.environ["JLU_DATABASE_URL"] = "sqlite://"
    os.environ["JLU_APP_DATA_DIR"] = str(output.parent / "runtime-offline")
    sys.path.insert(0, str(backend))
    # No app configuration, adapters, API, crawler or DB modules are imported.
    from app.parsers import parse_list_html, parse_detail_html
    from app.schemas.notice import NoticeCandidate
    import app.parsers.html as module
    assert Path(module.__file__).resolve().is_relative_to(backend)

    checks = []
    def snapshot(path, digest):
        raw = (EVIDENCE / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest, path
        checks.append(path)
        return raw.decode("utf-8")

    results = json.loads((EVIDENCE / "results.json").read_text(encoding="utf-8"))
    replay = []
    for r in results:
        groups = []
        if "POSSIBLE_NAVIGATION_CAPTURE" in r.get("issues", []):
            groups.append("navigation_suspect")
        if r["status"] == "完全通过":
            groups.append("positive_sample")
        if r.get("configured_source"):
            groups.append("configured")
        if r.get("priority") in {"P0", "P1"}:
            groups.append("high_value")
        if args.batch in {"b2", "b3", "b4"} and r["column_url"] == "https://spxy.jlu.edu.cn/bksjy/jxxx.htm":
            groups.append("food_encoding_control")
        if not groups:
            continue
        row = {"url": r["column_url"], "groups": groups, "original_status": r["status"],
               "original_checked_at": r["checked_at"], "original_issues": r.get("issues", []), "details": []}
        if not r.get("list_snapshot"):
            row.update(list_error="NO_SNAPSHOT: original access was blocked", list_count=None)
            replay.append(row)
            continue
        row["list_snapshot"] = r["list_snapshot"]
        try:
            items = parse_list_html(snapshot(r["list_snapshot"], r["list_sha256"]), r.get("final_url", r["column_url"]))
            row.update(list_count=len(items), list_urls=[i.url for i in items])
            if args.batch in {"b2", "b3", "b4"}:
                row["list_items"] = [dict(url=i.url, title=i.title, date=str(i.publish_date)) for i in items]
        except ValueError as exc:
            items = []
            row.update(list_count=0, list_error=f"{type(exc).__name__}: {exc}")
        for d in r.get("details", []):
            entry = {"url": d["url"], "original_checked_at": d.get("time"), "snapshot": d.get("snapshot"),
                     "snapshot_sha256": d.get("sha256")}
            if not d.get("snapshot"):
                entry.update(accepted=None, reason="NO_SNAPSHOT")
            else:
                item = next((i for i in items if i.url == d["url"]), None)
                if item is None:
                    raw = next((i for i in r.get("list_items", []) if i["url"] == d["url"]), None)
                    item = NoticeCandidate.model_validate(raw) if raw else NoticeCandidate(title=d.get("list_title") or "历史样本", url=d["url"])
                try:
                    parsed = parse_detail_html(snapshot(d["snapshot"], d["sha256"]), d["url"], item)
                    entry.update(accepted=True, title=parsed.title, date=str(parsed.publish_date),
                                 content_chars=len(parsed.content or ""), attachments=len(parsed.attachments),
                                 content_sha256=hashlib.sha256((parsed.content or "").encode()).hexdigest())
                    if args.batch in {"b3", "b4"}:
                        entry["parsed_attachments"] = [a.model_dump() for a in parsed.attachments]
                except ValueError as exc:
                    entry.update(accepted=False, reason=f"{type(exc).__name__}: {exc}")
            row["details"].append(entry)
        replay.append(row)
    value = {"replayed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "backend": str(backend),
             "parser_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
             "mode": "offline immutable snapshot replay; not fresh HTTP, attachment or Cloud validation",
             "network_requests": 0, "database_imported": any(n.startswith("app.database") for n in sys.modules),
             "snapshots_hash_verified": len(checks), "rows": replay,
             "groups": dict(Counter(g for r in replay for g in r["groups"]))}
    assert not value["database_imported"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in value.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
