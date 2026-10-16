"""Offline B5-B acceptance, preservation checks and disabled admission ledger."""
from datetime import datetime, timezone, timedelta
import difflib
import hashlib
import json
from pathlib import Path
import re

from jlu_date_evidence import assess_dates

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b5-b"
LIVE = OUT / "live-20261014"
REPLAY = OUT / "replay-final-20261014"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    time = datetime.now(timezone(timedelta(hours=8))).isoformat()
    before = read(OUT / "baseline-manifest.json")
    final = read(OUT / "final-manifest.json")
    for name, digest in final["source_hashes"].items():
        assert sha(ROOT / name) == digest, "Changed since final tests: " + name
    changed = [name for name, digest in final["source_hashes"].items()
               if name.startswith("backend/app/") and before["source_hashes"].get(name) != digest]
    assert set(changed) == {"backend/app/parsers/html.py", "backend/app/sources/generic.py"}
    patch = []
    for name in changed:
        old = Path(before["isolated_backend"]) / Path(name).relative_to("backend")
        patch.extend(difflib.unified_diff(old.read_text(encoding="utf-8").splitlines(True),
                     (ROOT / name).read_text(encoding="utf-8").splitlines(True), fromfile="B5-B baseline/" + name, tofile="B5-B final/" + name))
    (OUT / "application-changes.diff").write_text("".join(patch), encoding="utf-8")
    protected = read(ROOT / "docs/jlu-fix-b0-b1/tool-isolation-verification.json")["protected_hashes"]
    for name, digest in protected.items():
        assert sha(ROOT / name) == digest, name
    reports = {}
    for batch, title in [("b0-b1", "B0_B1"), ("b2", "B2"), ("b3", "B3"), ("b4", "B4"), ("b5-a", "B5_A")]:
        name = f"docs/JLU_SITE_FIX_{title}_REPORT.md"
        expected = read(ROOT / f"docs/jlu-fix-{batch}/acceptance.json")["files"][name]
        assert sha(ROOT / name) == expected, name
        reports[name] = expected
    source_hash = sha(ROOT / "backend/config/sources.yaml")
    assert source_hash == before["source_hashes"]["backend/config/sources.yaml"]
    assert source_hash == "d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d"
    html_checks = 0
    for directory in [LIVE, REPLAY]:
        for record in read(directory / "requests.json").values():
            if record.get("html_path"):
                assert sha(directory / record["html_path"]) == record["sha256"]
                html_checks += 1
    # The live manifest describes the capture-time code. Final code is checked
    # against the replay manifest; do not relabel old HTTP captures as new ones.
    manifest = read(REPLAY / "code-manifest.json")
    for name, digest in manifest["files"].items():
        path = LIVE / name.removeprefix("review-input/") if name.startswith("review-input/") else ROOT / name
        assert sha(path) == digest, name
    live = read(LIVE / "results.json")
    results = read(REPLAY / "results.json")
    assert len(results) == len(live) == 6
    for row, original in zip(results, live):
        assert row["id"] == original["id"] and row["verdict"] == original["verdict"]
        assert row["response"] == original["response"]
        assert all(d["structural_verified"] and not d["date_evidence"]["publication_verified"] for d in row["details"])
        assert len(row["details"]) == 3
        assert [d["response"] for d in row["details"]] == [d["response"] for d in original["details"]]
    # Reassess the eighteen B4 article snapshots without modifying old evidence.
    old_dir = ROOT / "docs/jlu-fix-b4/live-20261014"
    previous = []
    for row in read(old_dir / "results.json"):
        if not row["id"].startswith("yzb-"):
            continue
        for detail in row["details"]:
            path = old_dir / detail["snapshot"]
            assert sha(path) == detail["sha256"]
            previous.append({"id": row["id"], "url": detail["url"], "captured_at": detail["captured_at"],
                             "snapshot": str(path.relative_to(ROOT)), "sha256": detail["sha256"],
                             "date_evidence": assess_dates(path.read_text(encoding="utf-8"), list_date=detail["list_date"], parsed_date=detail["date"])})
    assert len(previous) == 18 and all(p["date_evidence"]["verdict"] == "UPDATE_TIME_ONLY_PUBLICATION_UNCONFIRMED" for p in previous)
    save("prior-snapshot-review.json", {"reviewed_at": time, "mode": "offline only", "details": previous})
    matrix = [{"id": r["id"], "url": r["url"], "column": r["column"], "captured_at": r["response"]["time"],
               "status": r["status"], "verdict": r["verdict"], "reason": r["reason"], "enabled": False,
               "list_count": r["list_count"], "details": [{"url": d["url"], "title": d["title"],
                    "captured_at": d["response"]["time"], "sha256": d["response"]["sha256"],
                    "snapshot": "replay-final-20261014/" + d["response"]["html_path"],
                    "selection": d["selection"], "list_dom": d["list_dom"], "date_evidence": d["date_evidence"],
                    "structural_verified": d["structural_verified"]} for d in r["details"]]} for r in results]
    save("date-matrix.json", matrix)
    candidates = read(ROOT / "docs/jlu-fix-b4/source-candidates.json")
    decisions = []
    for row in results:
        candidate = next(c for c in candidates if c["id"] == row["id"])
        assert not candidate["config"]["enabled"]
        decisions.append({"id": row["id"], "config": candidate["config"], "enabled": False,
                          "admission": "DEFERRED_DATE_SEMANTICS_UNCONFIRMED", "reason": row["reason"],
                          "date_evidence": "date-matrix.json", "next_requirement": "Explicit official publication metadata or a separately reviewed missing-date policy; no automatic migration"})
    save("admission-decisions.json", {"time": time, "candidate_sources_only": decisions, "formal_admissions": 0})
    summary = read(REPLAY / "summary.json")
    assert summary["http_attempts_this_session"] == summary["database_connection_attempts"] == 0
    assert summary["publication_verified_details"] == 0 and summary["structurally_verified_details"] == 18
    tests = {"baseline": "399 passed, 1 skipped", "regression-before": "10 failed, 236 passed",
             "targeted": "246 passed", "final": "415 passed, 1 skipped"}
    for label, expected in tests.items():
        assert expected in (OUT / (label + "-tests.log")).read_text(encoding="utf-8"), label
    save("preservation.json", {"time": time, "changed_application_files": changed,
         "original_audit_files_unchanged": len(protected), "prior_reports_unchanged": reports,
         "sources_yaml_sha256": source_hash, "database": "isolated tests only; live/replay engine connection forbidden",
         "production_db_migrations": 0, "formal_admissions": 0})
    report = ROOT / "docs/JLU_SITE_FIX_B5_B_REPORT.md"
    for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        if not target.startswith(("http://", "https://", "#")) and target != "jlu-fix-b5-b/acceptance.json":
            assert (report.parent / target).exists(), target
    tracked = changed + ["backend/scripts/verify_jlu_b1.py", "backend/scripts/jlu_date_evidence.py",
                        "backend/scripts/probe_jlu_b5_b.py", "backend/scripts/finalize_jlu_b5_b.py",
                        "backend/tests/test_jlu_b5_b.py", "docs/JLU_SITE_FIX_B5_B_REPORT.md",
                        "docs/JLU_FAILURE_REMEDIATION_PLAN.md", "docs/JLU_SITE_FIX_PLAN.md"]
    save("acceptance.json", {"time": time, "status": "passed_with_six_disabled_date_unconfirmed_candidates",
         "tests": tests, "new_regression_cases": 16, "original_audit_files_unchanged": len(protected),
         "prior_reports_unchanged": len(reports), "html_hash_checks_live_and_replay": html_checks,
         "prior_b4_details_reviewed": len(previous), "columns_reviewed": 6, "details_previewed": 18,
         "structural_verified_details": 18, "publication_verified_details": 0,
         "formal_admissions": 0, "sources_unchanged": True, "cloud_production_verified": False,
         "network_requests_in_acceptance": 0, "report_links_exist": True,
         "files": {name: sha(ROOT / name) for name in tracked}})
    print((OUT / "acceptance.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
