"""Assemble B4 acceptance from saved evidence only; no application/DB imports."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b4"
REVIEW = OUT / "review-final-20261014"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    before = read(OUT / "replay-before.json")
    after = read(OUT / "replay-after.json")
    assert before["snapshots_hash_verified"] == after["snapshots_hash_verified"] == 145
    changes = []
    for old, new in zip(before["rows"], after["rows"]):
        assert old["url"] == new["url"]
        if old == new:
            continue
        # The scoped-title guard also corrects one saved, out-of-scope control.
        assert old["url"] == "https://yz.chsi.com.cn/" and old["original_status"] == "无需适配"
        normalized = json.loads(json.dumps(new))
        assert old["details"][1]["url"] == new["details"][1]["url"] == "https://gradadmission.zstu.edu.cn/info/1011/3395.htm"
        assert old["details"][1]["title"] == "一、招生类型 及学制"
        assert new["details"][1]["title"] == "浙江理工大学2027年硕士研究生招生简章"
        normalized["details"][1]["title"] = old["details"][1]["title"]
        assert normalized == old, "Unexpected parser change outside the reviewed title correction"
        changes.append({"column_url": old["url"], "detail_url": new["details"][1]["url"],
                        "field": "title", "before": old["details"][1]["title"], "after": new["details"][1]["title"],
                        "reason": "Body subsection is no longer promoted to article title; use original list fallback",
                        "scope": "external reference, not a JLU source admission"})
    assert len(before["rows"]) == len(after["rows"]) == 68 and len(changes) == 1
    assert not after["database_imported"] and after["network_requests"] == 0
    save("replay-summary.json", {"time": stamp, "rows_checked": 68, "rows_unchanged": 67, "reviewed_changes": changes,
                               "snapshot_hash_checks_each": 145, "all_list_fields_equal": True,
                               "dates_bodies_attachments_and_acceptance_equal": True,
                               "network_requests": 0, "database_imported": False})
    baseline, final = [read(OUT / (label + "-manifest.json")) for label in ("baseline", "final")]
    changed = []
    for name, sha in final["source_hashes"].items():
        assert digest(ROOT / name) == sha, "Source changed since final tests: " + name
        if name.startswith("backend/app/") and baseline["source_hashes"].get(name) != sha:
            changed.append(name)
    assert set(changed) == {"backend/app/parsers/html.py", "backend/app/sources/generic.py"}
    difference = []
    for name in changed:
        old = Path(baseline["isolated_backend"]) / Path(name).relative_to("backend")
        difference.extend(difflib.unified_diff(old.read_text(encoding="utf-8").splitlines(True),
                          (ROOT / name).read_text(encoding="utf-8").splitlines(True),
                          fromfile="B4 baseline/" + name, tofile="B4 final/" + name))
    (OUT / "application-changes.diff").write_text("".join(difference), encoding="utf-8")
    protected = read(ROOT / "docs/jlu-fix-b0-b1/tool-isolation-verification.json")["protected_hashes"]
    for name, sha in protected.items():
        assert digest(ROOT / name) == sha, "Original audit changed: " + name
    reports = {}
    for batch, name in [("b0-b1", "B0_B1"), ("b2", "B2"), ("b3", "B3")]:
        path = f"docs/JLU_SITE_FIX_{name}_REPORT.md"
        expected = read(ROOT / f"docs/jlu-fix-{batch}/acceptance.json")["files"][path]
        assert digest(ROOT / path) == expected, path
        reports[path] = expected
    source_hash = digest(ROOT / "backend/config/sources.yaml")
    assert source_hash == "d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d"
    save("preservation.json", {"time": stamp, "changed_application_files_since_b4_baseline": changed,
                             "historical_audit_files_unchanged": len(protected),
                             "prior_report_hashes": reports, "sources_yaml_sha256": source_hash,
                             "current_sources_match_final_test_manifest": True, "database": "sqlite://"})
    candidates = read(OUT / "source-candidates.json")
    results = read(REVIEW / "results.json")
    assert len(candidates) == len(results) == 19
    assert len({c["config"]["base_url"] for c in candidates}) == 19
    assert all(c["config"]["enabled"] is False and not c["config"]["allow_private_network"] for c in candidates)
    assert "candidate_sources_only:" in (OUT / "source-candidates.yaml").read_text(encoding="utf-8")
    assert all(not r["enabled"] and not r["history_verified"] and not r["cloud_production_verified"] for r in results)
    for name, sha in read(REVIEW / "code-manifest.json")["files"].items():
        if name.startswith(("backend/", "docs/")):
            assert digest(ROOT / name) == sha, name
    html_checks = prefix_checks = 0
    for r in results:
        for entry, path_key, sha_key in [(r, "list_snapshot", "list_sha256")] + [(d, "snapshot", "sha256") for d in r["details"]]:
            if entry.get(path_key):
                assert digest(REVIEW / entry[path_key]) == entry[sha_key]
                html_checks += 1
        for p in r["attachment_probes"]:
            assert not p["complete_download_verified"]
            if p.get("prefix_path"):
                assert digest(REVIEW / p["prefix_path"]) == p["prefix_sha256"]
                assert p["read_bytes"] <= 4096
                prefix_checks += 1
    admissions = []
    for r in results:
        issues = sorted(set(r["issues"] + [i for d in r["details"] for i in d.get("issues", [])]))
        admissions.append({"id": r["id"], "url": r["url"], "captured_at": r["captured_at"],
                           "reviewed_at": r["validated_at"], "status": r["status"], "content_verdict": r["verdict"],
                           "enabled": False, "formal_admission": False,
                           "next_action": "B5 bounded pagination and runtime admission" if r["verdict"] == "CONTENT_SAMPLE_PASSED"
                               else "Confirm publication date semantics before admission" if "DATE_SEMANTICS" in r["verdict"]
                               else "Resolve documented access restriction before parser admission",
                           "remaining_issues": issues, "evidence_file": r["evidence_file"]})
    save("admission-decisions.json", admissions)
    csv_check = read(OUT / "csv-check.json")
    assert csv_check["status"] == "passed" and csv_check["csv_sha256"] == digest(REVIEW / "compatibility-report.csv")
    report = ROOT / "docs/JLU_SITE_FIX_B4_REPORT.md"
    for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        if not target.startswith(("https://", "http://", "#")) and target != "jlu-fix-b4/acceptance.json":
            assert (report.parent / target.split("#")[0]).exists(), target
    counts = {}
    for label, expected in [("baseline", "350 passed, 1 skipped"), ("targeted", "197 passed"), ("final", "365 passed, 1 skipped")]:
        log = (OUT / (label + "-tests.log")).read_text(encoding="utf-8")
        assert expected in log
        counts[label] = expected
    files = {name: digest(ROOT / name) for name in changed + ["backend/scripts/validate_jlu_b4.py",
             "backend/scripts/finalize_jlu_b4.py", "docs/JLU_SITE_FIX_B4_REPORT.md",
             "docs/jlu-fix-b4/review-final-20261014/results.json", "docs/jlu-fix-b4/review-final-20261014/compatibility-report.csv"]}
    save("acceptance.json", {"time": stamp, "status": "passed", "tests": counts,
         "states": dict(Counter(r["status"] for r in results)), "candidate_count": 19, "formal_admissions": 0,
         "detail_attempts": sum(len(r["details"]) for r in results),
         "strictly_verified_details": sum(r.get("verified_details", 0) for r in results),
         "structurally_verified_details": sum(r.get("structurally_verified_details", 0) for r in results),
         "prefix_categories": dict(Counter(p["category"] for r in results for p in r["attachment_probes"])),
         "html_hash_checks": html_checks, "prefix_hash_checks": prefix_checks,
         "historical_rows_checked": 68, "historical_rows_unchanged": 67, "external_title_corrections": 1,
         "protected_files_unchanged": len(protected),
         "csv_json_consistent": True, "report_links_exist": True, "sources_unchanged": True,
         "complete_downloads": 0, "network_requests_in_acceptance": 0, "files": files})
    print((OUT / "acceptance.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
