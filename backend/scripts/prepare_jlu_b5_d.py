"""Prepare bounded B5-D attachment work from saved evidence only."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b5-d"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    time = datetime.now(timezone(timedelta(hours=8))).isoformat()
    inputs = ["docs/jlu-fix-b3/attachment-matrix.json", "docs/jlu-fix-b4/review-final-20261014/results.json",
              "docs/jlu-fix-b5-c/replay-final-20261014/results.json", "docs/jlu-audit-evidence/results.json"]
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs}
    history = {}
    observations = [(p, "B3", ROOT / "docs/jlu-fix-b3") for p in read(ROOT / inputs[0])]
    observations.extend((p, "B4", ROOT / "docs/jlu-fix-b4") for r in read(ROOT / inputs[1]) for p in r["attachment_probes"])
    for probe, stage, root in observations:
        row = {"stage": stage, "probe": probe, "captured_at": probe["time"], "prefix_evidence": None}
        if probe.get("prefix_path"):
            digest = probe["prefix_sha256"]
            paths = sorted(root.glob("*/prefix/" + digest + ".bin"))
            assert paths, digest
            assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p in paths)
            row["prefix_evidence"] = paths[0].relative_to(ROOT).as_posix()
        history[probe["url"]] = row
    assert len(history) == 25
    assert Counter(v["probe"]["category"] for v in history.values()) == {"CAPTCHA_REQUIRED": 17, "FILE_PREFIX_VERIFIED": 7, "ROBOTS_BLOCKED": 1}
    save("prior-probes.json", {"prepared_at": time, "mode": "historical evidence, not new HTTP", "unique_endpoints": history,
                              "categories": dict(Counter(v["probe"]["category"] for v in history.values()))})
    previous = read(ROOT / inputs[2])
    plan = []
    for row in previous:
        details = row["details"]
        files = []
        seen = set()
        for detail in details:
            record = detail.get("response", {})
            if record.get("html_path"):
                path = ROOT / "docs/jlu-fix-b5-c/replay-final-20261014" / record["html_path"]
                assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
            for attachment in detail.get("parsed", {}).get("attachments", []):
                if attachment["url"] not in seen:
                    seen.add(attachment["url"])
                    files.append({**attachment, "article_url": detail["url"], "article_captured_at": record["time"],
                                  "article_snapshot": "docs/jlu-fix-b5-c/replay-final-20261014/" + record["html_path"], "article_sha256": record["sha256"]})
        known = next((f for f in files if f["url"] in history), None)
        selected = known or (files[0] if files else None)
        sampled = {d["url"] for d in details}
        extra = [i for i in row.get("items", []) if i["url"] not in sampled][:2] if not files else []
        plan.append({"id": row["id"], "url": row["url"], "column": row["column"], "kind": row["kind"], "config": row["config"],
                     "content_pagination_incremental_verdict": row["verdict"], "prior_details": details, "extracted_files": files,
                     "selected_attachment": selected, "reuse_prior_probe": bool(known), "extra_details_limit": 2,
                     "extra_details": extra, "deferred": row["id"] == "existing-oa-0", "enabled": False})
    assert len(plan) == 17 and not any(r["id"].startswith("yzb-") for r in plan)
    save("probe-plan.json", plan)
    originals = [r for r in read(ROOT / inputs[3]) if "ATTACHMENT_ENDPOINT_FAILED" in r.get("issues", [])]
    assert len(originals) == 108
    planned_urls = {r["url"] for r in plan}
    save("original-attachment-scope.json", {"original_tagged_columns": 108,
         "planned_columns_in_original_108": [r["column_url"] for r in originals if r["column_url"] in planned_urls],
         "deferred_columns": [{"url": r["column_url"], "institution": r["institution"], "priority": r["priority"],
                               "reason": "Outside B5-D bounded admission batch; historical attachment endpoint tag is not proof of damage"}
                              for r in originals if r["column_url"] not in planned_urls]})
    # Read the existing client's status cache only; never connect its SQLite or
    # trigger a crawl. No credentials, private-source entries or full logs copied.
    cache = Path(os.environ["LOCALAPPDATA"]) / "JLU Notice Monitor/cache/crawler_status.json"
    if cache.exists():
        status = read(cache)
        allowed = {r["config"]["code"] for r in plan if r["kind"] == "existing"}
        save("installed-desktop-observation.json", {"observed_at": time, "mode": "read-only prior installed-client cache; not a new execution of repaired code",
             "cache_sha256": hashlib.sha256(cache.read_bytes()).hexdigest(), "recorded_last_run_utc": status.get("last_run"),
             "overall_status": status.get("status"), "formal_database_access": False,
             "source_results": [{"source": r["source"], "status": r["status"], "execution_policy": r["execution_policy"],
                                 "effective_execution": r["effective_execution"], "fallback_used": r.get("fallback_used"), "fallback_reason": r.get("fallback_reason"),
                                 "attempts": [{k: v for k, v in a.items() if k != "error"} for a in r.get("attempts", [])]}
                                for r in status.get("source_results", []) if r["source"] in allowed]})
    save("preparation-manifest.json", {"time": time, "files": hashes, "network_requests": 0, "formal_database_access": False,
         "prior_probes": 25, "planned_columns": 17, "possible_fresh_prefix_probes": sum(bool(r["selected_attachment"]) and not r["reuse_prior_probe"] for r in plan),
         "extra_detail_previews_max": sum(len(r["extra_details"]) for r in plan if not r["deferred"])})
    print((OUT / "preparation-manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
