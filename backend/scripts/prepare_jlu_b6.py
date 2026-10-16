"""Freeze the complete P2 scope; preserve all old evidence, no network or DB."""
import csv
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b6"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / "targets.json").exists(), "Preparation already saved"
    rows = list(csv.DictReader((ROOT / "docs/jlu-compatibility-report.csv").open(encoding="utf-8-sig")))
    targets = []
    for row in rows:
        if row["priority"] != "P2":
            continue
        evidence = json.loads((ROOT / row["evidence_file"]).read_text(encoding="utf-8"))
        targets.append({"id": "p2-" + hashlib.sha256(row["column_url"].encode()).hexdigest()[:12],
                        "url": row["column_url"], "institution": row["institution"], "column": row["column"],
                        "site_url": row["site_url"], "old_status": row["status"], "old_issues": row["issues"],
                        "original_evidence": row["evidence_file"], "discovery_url": row["discovery_url"],
                        "original_snapshot": evidence.get("list_snapshot"),
                        "original_capture_time": row["checked_at"],
                        "config": {"code": "candidate-jlu-p2-" + hashlib.sha256(row["column_url"].encode()).hexdigest()[:12],
                                   "name": row["institution"] + " / " + row["column"], "base_url": row["column_url"],
                                   "parser": "generic_html", "enabled": False, "auth_type": "none",
                                   "allow_private_network": False, "validation_scope": "local",
                                   "execution_policy": "cloud_preferred", "parser_config": {"pagination_limit": 2}}})
    assert len(targets) == 164 and len({t["url"] for t in targets}) == 164
    (OUT / "targets.json").write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8")
    # The baseline just completed before the user expanded the scope; no app changes since.
    for suffix in ["manifest.json", "tests.log"]:
        shutil.copy2(ROOT / ("docs/jlu-fix-b6-a/baseline-" + suffix), OUT / ("baseline-" + suffix))
    protected = json.loads((ROOT / "docs/jlu-fix-b0-b1/tool-isolation-verification.json").read_text(encoding="utf-8"))["protected_hashes"]
    reports = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "docs").glob("JLU_SITE_FIX_*_REPORT.md")}
    baseline = json.loads((OUT / "baseline-manifest.json").read_text(encoding="utf-8"))
    for p, digest in baseline["source_hashes"].items():
        if p.startswith(("backend/app/", "backend/config/")):
            assert sha(ROOT / p) == digest
    value = {"scope": "All 164 original P2 entries: 30 failures + 127 partial + 7 sample passes; B7 excluded",
             "baseline_origin": "B6-A isolated baseline, completed before scope expanded; app/config unchanged",
             "tests": "487 passed, 1 skipped", "protected_hashes": protected, "prior_reports": reports,
             "inputs": {p: sha(ROOT / p) for p in ["docs/jlu-compatibility-report.csv", "docs/jlu-failure-summary.json", "docs/jlu-fix-b6/targets.json"]}}
    (OUT / "preparation.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"targets": len(targets), "old_failures": sum(t["old_status"] == "失败" for t in targets), "prior_reports": len(reports)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
