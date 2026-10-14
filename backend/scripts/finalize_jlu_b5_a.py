"""Offline B5-A acceptance: preserve prior evidence and verify local artifacts."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import difflib
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b5-a"
FOLLOW = OUT / "followup-20261014"


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
    changed = [name for name, digest in final["source_hashes"].items() if name.startswith("backend/app/") and before["source_hashes"].get(name) != digest]
    assert set(changed) == {"backend/app/services/http_diagnostics.py", "backend/app/sources/base.py",
                           "backend/app/sources/generic.py", "backend/app/parsers/html.py"}
    patch = []
    for name in changed:
        old = Path(before["isolated_backend"]) / Path(name).relative_to("backend")
        patch.extend(difflib.unified_diff(old.read_text(encoding="utf-8").splitlines(True),
            (ROOT / name).read_text(encoding="utf-8").splitlines(True), fromfile="B5-A baseline/" + name, tofile="B5-A final/" + name))
    (OUT / "application-changes.diff").write_text("".join(patch), encoding="utf-8")
    protected = read(ROOT / "docs/jlu-fix-b0-b1/tool-isolation-verification.json")["protected_hashes"]
    for name, digest in protected.items():
        assert sha(ROOT / name) == digest
    reports = {}
    for batch, title in [("b0-b1", "B0_B1"), ("b2", "B2"), ("b3", "B3"), ("b4", "B4")]:
        name = f"docs/JLU_SITE_FIX_{title}_REPORT.md"
        expected = read(ROOT / f"docs/jlu-fix-{batch}/acceptance.json")["files"][name]
        assert sha(ROOT / name) == expected
        reports[name] = expected
    source_hash = sha(ROOT / "backend/config/sources.yaml")
    assert source_hash == before["source_hashes"]["backend/config/sources.yaml"]
    assert source_hash == "d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d"
    save("preservation.json", {"time": time, "changed_application_files": changed,
        "original_audit_files_unchanged": len(protected), "prior_reports_unchanged": reports,
        "sources_yaml_sha256": source_hash, "database_access": "isolated tests only; live guard blocks connections"})
    # Keep the initial run's finalization failure explicit rather than replacing it.
    save("first-run-finalization-error.json", {"run": "docs/jlu-fix-b5-a/live-20261014",
        "error": "AssertionError: expected no app.database modules imported",
        "phase": "after all network requests; summary finalization",
        "cause": "Source package eagerly imports registry and CloudFeedSource, which initializes an in-memory database engine",
        "impact": "HTTP evidence retained; no crawler or DB session called; initial summary not produced",
        "resolution": "Follow-up asserts sqlite:// and rejects any actual engine connection; cached capture times preserved"})
    manifest = read(FOLLOW / "code-manifest.json")
    for name, digest in manifest["files"].items():
        path = ROOT / name if not name.startswith("reuse-input/") else OUT / "live-20261014" / name.removeprefix("reuse-input/")
        assert sha(path) == digest, name
    requests = read(FOLLOW / "requests.json")
    html_checks = 0
    for record in requests.values():
        if record.get("html_path"):
            assert sha(FOLLOW / record["html_path"]) == record["sha256"]
            html_checks += 1
    originals = read(ROOT / "docs/jlu-fix-b4/source-candidates.json")
    candidates, inspections = [], []
    for alternate in read(FOLLOW / "alternatives.json"):
        assert alternate["category"] == "HTTP_CONTENT_AVAILABLE_NOT_ADMITTED"
        url = alternate["url"]
        original = next(c for c in originals if c["config"]["base_url"] == url.rstrip("/"))
        home = next(h for h in read(FOLLOW / "home-observations.json") if h["url"] == alternate["discovery_url"])
        soup = BeautifulSoup((FOLLOW / home["response"]["html_path"]).read_text(encoding="utf-8"), "html.parser")
        assert any(a.get("href") == url for a in soup.select("a[href]")), "No exact official home link"
        page = BeautifulSoup((FOLLOW / alternate["response"]["html_path"]).read_text(encoding="utf-8"), "html.parser")
        title = page.title.get_text(strip=True) if page.title else ""
        links = [{"title": a.get_text(" ", strip=True), "href": a["href"]} for a in page.select("h3 a[href]")
                 if re.search(r"/html/.+\.html$", a["href"])]
        assert "通知公告" in title and links
        inspections.append({"url": url, "captured_at": alternate["response"]["time"], "page_title": title,
            "article_links_in_h3": links, "official_home_link_verified": True,
            "scope": "access + bounded DOM inspection only; no detail/date/attachment/pagination or Cloud admission"})
        value = json.loads(json.dumps(original))
        value["original_base_url"] = value["config"]["base_url"]
        value["config"]["base_url"] = url
        value["support_status"] = "ACCESS_ONLY_NOT_ADMITTED_DISABLED"
        value["discovery_url"] = alternate["discovery_url"]
        value["discovery_basis"] = "Exact trailing-slash URL observed in official home anchor and fetched unchanged"
        value["scope"] = inspections[-1]["scope"]
        value["captured_at"] = alternate["response"]["time"]
        assert not value["config"]["enabled"]
        candidates.append(value)
    assert len(candidates) == 2
    save("corrected-disabled-candidates.json", {"candidate_sources_only": candidates, "formal_admissions": 0})
    save("alternative-dom-inspection.json", inspections)
    summary = read(FOLLOW / "summary.json")
    assert summary["database_url"] == "sqlite://" and summary["database_connection_attempts"] == 0
    tests = {"baseline": "365 passed, 1 skipped", "regression-before": "20 failed, 210 passed",
             "targeted": "231 passed", "final": "399 passed, 1 skipped"}
    for label, expected in tests.items():
        assert expected in (OUT / (label + "-tests.log")).read_text(encoding="utf-8")
    report = ROOT / "docs/JLU_SITE_FIX_B5_A_REPORT.md"
    for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        if not target.startswith(("http://", "https://", "#")) and target != "jlu-fix-b5-a/acceptance.json":
            assert (report.parent / target).exists(), target
    save("acceptance.json", {"time": time, "status": "passed", "tests": tests,
        "changed_application_files": changed, "original_audit_files_unchanged": len(protected),
        "previous_reports_unchanged": 4, "sources_unchanged": True, "formal_admissions": 0,
        "html_hash_checks": html_checks, "corrected_disabled_candidates": len(candidates),
        "live_case_categories": summary["categories"], "database_connection_attempts_followup": 0,
        "network_requests_in_acceptance": 0, "report_links_exist": True,
        "files": {name: sha(ROOT / name) for name in changed + ["backend/scripts/audit_jlu_sites.py",
            "backend/scripts/probe_jlu_b5_a.py", "backend/tests/test_jlu_b5_a.py", "docs/JLU_SITE_FIX_B5_A_REPORT.md"]}})
    print((OUT / "acceptance.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
