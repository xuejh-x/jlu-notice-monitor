"""Freeze B7 inputs and preserve prior evidence; no application imports or I/O to DB."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b7"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / "preparation.json").exists(), "Already prepared"
    rows = list(csv.DictReader((ROOT / "docs/jlu-compatibility-report.csv").open(encoding="utf-8-sig")))
    targets = []
    for row in rows:
        if row["priority"] != "P3":
            continue
        key = hashlib.sha256(row["column_url"].encode()).hexdigest()[:12]
        targets.append({"id": "p3-" + key, "url": row["column_url"], "institution": row["institution"],
            "column": row["column"], "site_url": row["site_url"], "priority": "P3", "old_status": row["status"],
            "old_issues": row["issues"], "original_evidence": row["evidence_file"],
            "original_capture_time": row["checked_at"], "discovery_url": row["discovery_url"],
            "config": {"code": "candidate-jlu-p3-" + key, "name": row["institution"] + " / " + row["column"],
                "base_url": row["column_url"], "parser": "generic_html", "enabled": False, "auth_type": "none",
                "allow_private_network": False, "validation_scope": "local", "execution_policy": "cloud_preferred",
                "parser_config": {"pagination_limit": 2}}})
    assert len(targets) == 112 and len({t["url"] for t in targets}) == 112
    save("targets.json", targets)
    discovery = json.loads((ROOT / "docs/jlu-audit-evidence/discovery.json").read_text(encoding="utf-8"))
    gaps = [r for r in discovery if r["status"] in {"unreachable", "no_column_discovered"}]
    assert len(gaps) == 59
    save("discovery-targets.json", gaps)
    units = json.loads((ROOT / "docs/jlu-audit-evidence/units.json").read_text(encoding="utf-8"))
    unknown = [u for u in units if not u["site_url"]]
    save("unknown-unit-targets.json", unknown)
    protected = json.loads((ROOT / "docs/jlu-fix-b0-b1/tool-isolation-verification.json").read_text(encoding="utf-8"))["protected_hashes"]
    # Preserve all accepted B6 records as well as the earlier audit and reports.
    b6 = {p.relative_to(ROOT).as_posix(): digest(p) for p in (ROOT / "docs/jlu-fix-b6").rglob("*") if p.is_file()}
    reports = {p.relative_to(ROOT).as_posix(): digest(p) for p in (ROOT / "docs").glob("JLU_SITE_FIX_*_REPORT.md")}
    save("preparation.json", {"targets": len(targets), "discovery_gaps": len(gaps), "unknown_unit_rows": len(unknown),
        "protected_hashes": protected, "prior_reports": reports, "protected_b6": b6,
        "formal_yaml_sha256": digest(ROOT / "backend/config/sources.yaml"),
        "inputs": {n: digest(OUT / n) for n in ["targets.json", "discovery-targets.json", "unknown-unit-targets.json"]},
        "scope": "Entire B7 bounded public audit; OA deferred; no formal admission, deployment or downloads"})
    print(json.dumps({"targets": len(targets), "gaps": len(gaps), "unknown": len(unknown), "prior_reports": len(reports)}))


if __name__ == "__main__":
    main()
