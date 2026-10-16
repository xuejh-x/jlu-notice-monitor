"""Offline B5-C acceptance, evidence preservation and admission matrix."""
from datetime import datetime, timezone, timedelta
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b5-c"
REPLAY = OUT / "replay-final-20261014"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    time = datetime.now(timezone(timedelta(hours=8))).isoformat()
    before, final = read(OUT / "baseline-manifest.json"), read(OUT / "final-manifest.json")
    # Artifact-processing scripts may be finalized after the suite. Its
    # application, config and test inputs must still match exactly.
    for name, digest in final["source_hashes"].items():
        if name.startswith(("backend/app/", "backend/config/", "backend/tests/")):
            assert sha(ROOT / name) == digest, name
    changed = [name for name, digest in final["source_hashes"].items()
               if name.startswith("backend/app/") and before["source_hashes"].get(name) != digest]
    assert set(changed) == {"backend/app/parsers/html.py", "backend/app/sources/generic.py", "backend/app/sources/base.py",
                            "backend/app/services/list_pagination.py", "backend/app/services/deduplication.py", "backend/app/crawler/runner.py"}
    patch = []
    for name in changed:
        old = Path(before["isolated_backend"]) / Path(name).relative_to("backend")
        patch.extend(difflib.unified_diff(old.read_text(encoding="utf-8").splitlines(True) if old.exists() else [],
                     (ROOT / name).read_text(encoding="utf-8").splitlines(True), fromfile="B5-C baseline/" + name, tofile="B5-C final/" + name))
    (OUT / "application-changes.diff").write_text("".join(patch), encoding="utf-8")
    protected = read(ROOT / "docs/jlu-fix-b0-b1/tool-isolation-verification.json")["protected_hashes"]
    for name, digest in protected.items():
        assert sha(ROOT / name) == digest, name
    reports = {}
    for batch, title in [("b0-b1", "B0_B1"), ("b2", "B2"), ("b3", "B3"), ("b4", "B4"), ("b5-a", "B5_A"), ("b5-b", "B5_B")]:
        name = f"docs/JLU_SITE_FIX_{title}_REPORT.md"
        expected = read(ROOT / f"docs/jlu-fix-{batch}/acceptance.json")["files"][name]
        assert sha(ROOT / name) == expected, name
        reports[name] = expected
    source_hash = sha(ROOT / "backend/config/sources.yaml")
    assert source_hash == before["source_hashes"]["backend/config/sources.yaml"] == "d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d"
    candidate_file = "docs/jlu-fix-b4/source-candidates.json"
    candidate_hash = read(ROOT / "docs/jlu-fix-b5-b/replay-final-20261014/code-manifest.json")["files"][candidate_file]
    assert sha(ROOT / candidate_file) == candidate_hash
    manifest = read(REPLAY / "code-manifest.json")
    input_dir = ROOT / manifest["input_dir"]
    for name, digest in manifest["files"].items():
        if name == "mode":
            continue
        path = input_dir / name.removeprefix("input/") if name.startswith("input/") else ROOT / name
        assert sha(path) == digest, name
    stage_info, html_checks, all_times = [], 0, []
    for stage in ["discovery-20261014", "live-20261014", "followup-20261014", "final-live-20261014", "replay-final-20261014"]:
        directory = OUT / stage
        records = read(directory / "requests.json")
        for record in records.values():
            if record.get("html_path"):
                assert sha(directory / record["html_path"]) == record["sha256"]
                html_checks += 1
            if record.get("time"):
                all_times.append(record["time"])
        http = directory / "http.jsonl"
        responses = len(http.read_text(encoding="utf-8").splitlines()) if http.exists() else 0
        attempts = 4 if stage == "live-20261014" else read(directory / "summary.json").get("http_attempts", read(directory / "summary.json").get("http_attempts_this_session", 0))
        stage_info.append({"stage": stage, "http_attempts": attempts, "http_responses": responses})
    rows, summary = read(REPLAY / "results.json"), read(REPLAY / "summary.json")
    assert len(rows) == 17 and not any(r["id"].startswith("yzb-") for r in rows)
    assert summary["statuses"] == {"部分通过": 16, "失败": 1}
    assert summary["list_pages"] == 45 and summary["list_items"] == 575
    assert summary["details"] == summary["verified_details"] == 48
    assert summary["database_sample_replays"] == 16 and not summary["unexpected_merges"]
    assert summary["http_attempts_this_session"] == summary["app_database_connections"] == 0
    for row in rows:
        if row["verdict"] == "ACCESS_BLOCKED":
            assert row["id"] == "existing-oa-0" and not row["details"]
            continue
        assert row["pagination_verified"] and not row["observed_next_missed_by_selector"]
        assert len(row["pages"]) <= 3 and row["list_count"] <= 90 and len(row["details"]) == 3
        replay = row["database_replay"]
        assert replay["passed"] and not replay["unexpected_merge_requires_review"] and replay["favorites_preserved"]
        assert replay["second_round"]["new_count"] == replay["second_round"]["updated_count"] == 0
        assert replay["second_round"]["detail_skipped"] == replay["sampled_candidates"]
    old_rows = read(OUT / "followup-20261014/results.json")
    before_identity = next(r for r in old_rows if r["id"] == "existing-cse-1")["database_replay"]
    after_identity = next(r for r in rows if r["id"] == "existing-cse-1")["database_replay"]
    assert before_identity["notice_count"] == 2 and after_identity["notice_count"] == 3
    duplicates = read(OUT / "duplicate-classification.json")
    assert duplicates["summary"]["original_counts_reproduced"] and duplicates["summary"]["same_url_groups"] == 113 and duplicates["summary"]["title_date_candidates"] == 48
    for name, digest in duplicates["input_hashes"].items():
        assert sha(ROOT / name) == digest
    matrix = [{"id": r["id"], "url": r["url"], "column": r["column"], "kind": r["kind"], "checked_at": r["checked_at"],
               "status": r["status"], "reason": r["reason"], "verdict": r["verdict"], "new_admission": False,
               "local_readonly_preview": True, "actual_cloud_verified": False, "actual_desktop_fallback_verified": False,
               "pages": r.get("pages", []), "pagination": r.get("pagination", []), "details": r["details"],
               "database_replay": r.get("database_replay"), "formal_configuration_changed": False} for r in rows]
    save("admission-matrix.json", matrix)
    save("validation-refinement-notes.json", {"time": time, "initial_run_serialization": "See first-run-finalization-error.json; requests retained",
         "first_validation_selector_misses": ["existing-csw-0", "existing-csw-1", "existing-innovation-0", "international"],
         "resolution": "Use observed old-style a.Next markup and reject acceptance when an observed next URL is missed by the selector",
         "dedup_before_after": {"sample": "CSE summer training notices (one)/(two)", "candidate_count": 3, "before_notices": 2, "after_notices": 3},
         "duplicate_reconstruction_input": "Reviewed original results.json, same input used by original export; per-column snapshots retain earlier observations"})
    save("preservation.json", {"time": time, "changed_application_files": changed, "original_audit_files_unchanged": len(protected),
         "prior_reports_unchanged": reports, "sources_yaml_sha256": source_hash, "b4_candidates_sha256": candidate_hash,
         "formal_admissions": 0, "production_database_connections": 0, "production_db_migrations": 0})
    tests = {"baseline": "415 passed, 1 skipped", "regression-before": "20 failed, 266 passed", "form-regression-before": "1 failed, 299 passed",
             "identity-regression-before": "3 failed, 300 passed", "pdf-regression-before": "5 failed, 304 passed",
             "targeted": "310 passed", "final": "465 passed, 1 skipped"}
    for label, expected in tests.items():
        assert expected in (OUT / f"{label}-tests.log").read_text(encoding="utf-8"), label
    report = ROOT / "docs/JLU_SITE_FIX_B5_C_REPORT.md"
    for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        if not target.startswith(("http://", "https://", "#")) and target != "jlu-fix-b5-c/acceptance.json":
            assert (report.parent / target).exists(), target
    related = changed + ["backend/scripts/verify_jlu_b1.py", "backend/tests/test_jlu_b5_c.py", "backend/tests/fixtures/jlu_b5_c/employment-pagination.html",
                        "backend/scripts/discover_jlu_b5_c.py", "backend/scripts/validate_jlu_b5_c.py", "backend/scripts/classify_jlu_b5_c_duplicates.py",
                        "backend/scripts/finalize_jlu_b5_c.py", "docs/JLU_SITE_FIX_B5_C_REPORT.md", "docs/JLU_FAILURE_REMEDIATION_PLAN.md", "docs/JLU_SITE_FIX_PLAN.md"]
    save("acceptance.json", {"time": time, "status": "bounded_B5_C_complete_with_OA_blocked_and_no_formal_admissions", "tests": tests,
         "new_test_cases": 50, "columns_attempted": 17, "bounded_sample_passed": 16, "access_blocked": 1,
         "pages_checked": 45, "list_occurrences": 575, "details_verified": 48, "isolated_two_round_source_replays": 16,
         "same_url_groups_reproduced": 113, "title_date_candidates_reproduced": 48, "formal_merges": 0,
         "old_audit_files_preserved": len(protected), "prior_reports_preserved": len(reports), "snapshot_copy_hash_checks": html_checks,
         "capture_time_range": [min(all_times), max(all_times)], "network_stages": stage_info,
         "http_attempts_total": sum(r["http_attempts"] for r in stage_info), "http_responses_total": sum(r["http_responses"] for r in stage_info),
         "network_in_acceptance": 0, "formal_sources_changed": 0, "formal_admissions": 0, "production_database_connections": 0,
         "cloud_production_verified": False, "attachment_file_downloads": 0, "report_links_exist": True,
         "files": {name: sha(ROOT / name) for name in related}})
    print((OUT / "acceptance.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
