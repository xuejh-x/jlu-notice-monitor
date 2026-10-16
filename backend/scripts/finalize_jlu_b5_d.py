"""Offline B5-D admission matrix and immutable-evidence acceptance."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

os.environ["JLU_DATABASE_URL"] = "sqlite://"
from app.config import get_settings
from app.services.attachment_validation import classify_attachment_prefix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b5-d"
LIVE = OUT / "live-20261015"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    time = datetime.now(timezone(timedelta(hours=8))).isoformat()
    baseline, final = read(OUT / "baseline-manifest.json"), read(OUT / "final-manifest.json")
    for name, digest in final["source_hashes"].items():
        if name.startswith(("backend/app/", "backend/config/", "backend/tests/")):
            assert sha(ROOT / name) == digest, name
    changed = [name for name, digest in final["source_hashes"].items() if name.startswith("backend/app/") and baseline["source_hashes"].get(name) != digest]
    assert changed == ["backend/app/services/attachment_validation.py"]
    name = changed[0]
    before = Path(baseline["isolated_backend"]) / Path(name).relative_to("backend")
    (OUT / "application-changes.diff").write_text("".join(difflib.unified_diff(before.read_text(encoding="utf-8").splitlines(True),
        (ROOT / name).read_text(encoding="utf-8").splitlines(True), fromfile="B5-D baseline/" + name, tofile="B5-D final/" + name)), encoding="utf-8")
    protected = read(ROOT / "docs/jlu-fix-b0-b1/tool-isolation-verification.json")["protected_hashes"]
    for path, digest in protected.items():
        assert sha(ROOT / path) == digest, path
    reports = {}
    for batch, title in [("b0-b1", "B0_B1"), ("b2", "B2"), ("b3", "B3"), ("b4", "B4"), ("b5-a", "B5_A"), ("b5-b", "B5_B"), ("b5-c", "B5_C")]:
        path = f"docs/JLU_SITE_FIX_{title}_REPORT.md"
        digest = read(ROOT / f"docs/jlu-fix-{batch}/acceptance.json")["files"][path]
        assert sha(ROOT / path) == digest, path
        reports[path] = digest
    assert sha(ROOT / "backend/config/sources.yaml") == baseline["source_hashes"]["backend/config/sources.yaml"] == "d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d"
    assert subprocess.run(["git", "diff", "--quiet", "--", "frontend"], cwd=ROOT).returncode == 0
    for path, digest in read(OUT / "preparation-manifest.json")["files"].items():
        assert sha(ROOT / path) == digest, path
    for path, digest in read(LIVE / "code-manifest.json")["files"].items():
        assert sha(ROOT / path) == digest, path
    summary = read(LIVE / "summary.json")
    assert summary["fresh_unique_endpoints"] == 2 and summary["fresh_categories"] == {"FILE_PREFIX_VERIFIED": 1, "CAPTCHA_REQUIRED": 1}
    assert summary["app_database_connections"] == summary["oa_network_requests"] == summary["complete_downloads"] == 0
    requests = read(LIVE / "requests.json")
    raw_checks = 0
    for record in requests.values():
        for path_field, hash_field in [("html_path", "sha256"), ("prefix_path", "prefix_sha256")]:
            if record.get(path_field):
                assert sha(LIVE / record[path_field]) == record[hash_field]
                raw_checks += 1
    prior = read(OUT / "prior-probes.json")["unique_endpoints"]
    ledger = {}
    for url, value in prior.items():
        original = value["probe"]
        review = {"url": url, "captured_at": value["captured_at"], "reviewed_at": time, "mode": "HISTORICAL_OFFLINE_REVIEW",
                  "original_category": original["category"], "evidence_stage": value["stage"], "prefix_evidence": value["prefix_evidence"],
                  "original_probe": original, "range_header_available": False}
        if value["prefix_evidence"]:
            path = ROOT / value["prefix_evidence"]
            assert sha(path) == original["prefix_sha256"]
            review.update(classify_attachment_prefix(original["status"], {"content-type": original.get("content_type", "")},
                          path.read_bytes(), original.get("expected_type") or original.get("type", "")))
        else:
            review.update(category=original["category"], reason=original["reason"], file_prefix_verified=False, complete_download_verified=False)
        ledger[url] = review
    live_rows = read(LIVE / "results.json")
    for row in live_rows:
        probe = row["attachment_probe"]
        if not probe or probe["mode"] != "LIVE_BOUNDED_PREFIX":
            continue
        path = LIVE / probe["prefix_path"]
        assert sha(path) == probe["prefix_sha256"] and len(path.read_bytes()) <= 4096
        review = classify_attachment_prefix(probe["status"], probe["response_headers"], path.read_bytes(), probe["expected_type"])
        assert review["category"] == probe["category"]
        ledger[probe["url"]] = {**review, "url": probe["url"], "captured_at": probe["time"], "reviewed_at": time,
                               "mode": "LIVE_BOUNDED_PREFIX", "prefix_evidence": "docs/jlu-fix-b5-d/live-20261015/" + probe["prefix_path"],
                               "response_headers": probe["response_headers"], "range_header_available": "content-range" in probe["response_headers"]}
    assert len(ledger) == 27
    save("attachment-endpoint-ledger.json", {"time": time, "prior_unique_endpoints": 25, "new_unique_endpoints": 2,
         "total_unique_endpoints": 27, "reviewed_categories": dict(Counter(p["category"] for p in ledger.values())),
         "historical_category_changes": [u for u, p in ledger.items() if p.get("original_category") and p["original_category"] != p["category"]],
         "endpoints": ledger, "complete_downloads": 0})
    s = get_settings()
    admin_host = urlsplit(s.cloud_admin_url or "").hostname
    environment = {**read(LIVE / "environment-availability.json"), "reviewed_at": time,
         "configured_admin_is_loopback": admin_host in {"127.0.0.1", "localhost", "::1"},
         "actual_remote_cloud_endpoint_provided": bool(admin_host and admin_host not in {"127.0.0.1", "localhost", "::1"}),
         "cloud_feed_traffic_exercised": False, "cloud_control_tests_are_simulated": True,
         "installed_desktop_evidence": "installed-desktop-observation.json; historical cache only"}
    save("environment-review.json", environment)
    plans = {r["id"]: r for r in read(OUT / "probe-plan.json")}
    matrix = []
    for row in live_rows:
        plan = plans[row["id"]]
        probe = row["attachment_probe"]
        endpoint = ledger.get(probe["url"]) if probe else None
        decision = "DEFERRED_BY_USER" if plan["deferred"] else "HAS_CAPABILITY_LIMITS_NOT_FORMALLY_ADMITTED"
        category = endpoint["category"] if endpoint else row["verdict"]
        matrix.append({"id": row["id"], "institution": plan["config"]["name"], "column": row["column"], "url": row["url"],
             "reviewed_at": time, "decision": decision, "attachment_category": category,
             "attachment_evidence": endpoint, "extracted_attachment_references": plan["extracted_files"], "extra_detail_previews": row["extra_details"],
             "content_date_pagination_incremental": {"verdict": plan["content_pagination_incremental_verdict"], "evidence": "docs/jlu-fix-b5-c/replay-final-20261014/results.json", "mode": "prior saved bounded verification"},
             "windows_public_preview": "VERIFIED_WITH_RECORDED_LIMITS" if not plan["deferred"] else "NOT_RETESTED",
             "linux_cloud_crawl": "NOT_VERIFIED", "cloud_feed": "NOT_CONFIGURED", "desktop_fallback": "controlled tests + prior installed cache; no new installed-client crawl",
             "execution_policy_preserved": plan["config"].get("execution_policy"), "source_identity_changed": False,
             "formal_admission": False, "candidate_enabled": False, "complete_download_verified": False})
    assert len(matrix) == 17
    save("admission-matrix.json", matrix)
    tests = {"baseline": "465 passed, 1 skipped", "regression-before": "9 failed, 339 passed", "targeted": "348 passed", "final": "487 passed, 1 skipped"}
    for label, expected in tests.items():
        assert expected in (OUT / f"{label}-tests.log").read_text(encoding="utf-8"), label
    save("preservation.json", {"time": time, "changed_application_files": changed, "original_audit_files_unchanged": len(protected),
         "prior_reports_unchanged": reports, "sources_yaml_unchanged": True, "frontend_unchanged": True,
         "oa_status_and_api_code_unchanged_from_baseline": all(sha(ROOT / p) == baseline["source_hashes"][p] for p in ["backend/app/api/routes.py", "backend/app/api/source_management.py", "backend/app/sources/cloud.py"]),
         "production_database_connections_by_this_batch": 0, "system_network_changes": 0, "formal_admissions": 0})
    report = ROOT / "docs/JLU_SITE_FIX_B5_D_REPORT.md"
    for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        if not target.startswith(("http://", "https://", "#")) and target != "jlu-fix-b5-d/acceptance.json":
            assert (report.parent / target).exists(), target
    files = changed + ["backend/scripts/verify_jlu_b1.py", "backend/tests/test_jlu_b5_d.py", "backend/scripts/prepare_jlu_b5_d.py",
                     "backend/scripts/probe_jlu_b5_d.py", "backend/scripts/finalize_jlu_b5_d.py", "docs/JLU_SITE_FIX_B5_D_REPORT.md",
                     "docs/JLU_FAILURE_REMEDIATION_PLAN.md", "docs/JLU_SITE_FIX_PLAN.md"]
    save("acceptance.json", {"time": time, "status": "B5_D_bounded_validation_delivered_actual_cloud_admission_pending", "tests": tests, "new_test_cases": 22,
         "columns": 17, "limited_capability": 16, "deferred_OA": 1, "full_environment_admissions": 0,
         "prior_attachment_endpoints": 25, "new_attachment_endpoints": 2, "total_attachment_endpoints": 27,
         "combined_categories": dict(Counter(p["category"] for p in ledger.values())), "selected_categories": dict(Counter(r["attachment_category"] for r in matrix)),
         "http_attempts": summary["http_attempts_this_session"], "extra_details": summary["extra_detail_previews"],
         "complete_downloads": 0, "oa_requests": 0, "cloud_production_verified": False, "formal_admissions": 0,
         "original_audit_files_unchanged": len(protected), "prior_reports_unchanged": len(reports), "fresh_snapshot_hash_checks": raw_checks,
         "frontend_changed": False, "oa_status_repair_deferred": True, "production_db_connections": 0, "system_network_changes": 0,
         "files": {p: sha(ROOT / p) for p in files}})
    print((OUT / "acceptance.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
