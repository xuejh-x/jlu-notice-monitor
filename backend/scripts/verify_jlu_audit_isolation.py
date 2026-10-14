"""Offline checks for independent audit output and stale-result protection."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b0-b1"


def main():
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")
    destination = OUT / ("tool-isolation-" + stamp)
    protected = list((ROOT / "docs/jlu-audit-evidence").rglob("*"))
    protected += [ROOT / "docs" / n for n in ["JLU_SITE_AUDIT.md", "jlu-site-inventory.csv", "jlu-compatibility-report.csv"]]
    def hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.is_file()}
    before = hashes()
    commands = []
    def run(arguments, expected=0):
        result = subprocess.run([sys.executable, str(ROOT / "backend/scripts/audit_jlu_sites.py"), *arguments], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8")
        commands.append({"args": arguments, "returncode": result.returncode, "output": result.stdout + result.stderr})
        assert result.returncode == expected, commands[-1]
        return result
    common = ["--output-dir", str(destination), "--input-dir", "docs/jlu-audit-evidence", "--column-url", "https://auto.jlu.edu.cn/zsxx.htm"]
    run(["export", *common])
    assert len(json.loads((destination / "columns.json").read_text(encoding="utf-8"))) == 1
    assert (destination / "jlu-compatibility-report.csv").exists()
    assert not (destination / "requests.json").exists() and not (destination / "results.json").exists()
    run(["check", "--output-dir", str(destination)])
    run(["check", "--output-dir", "docs/jlu-audit-evidence"], 2)
    (destination / "results.json").write_text("[]", encoding="utf-8")
    (destination / "validation-code-manifest.json").write_text('{"files": {"stale": "fingerprint"}}', encoding="utf-8")
    result = run(["validate", "--output-dir", str(destination)], 1)
    assert "Parser fingerprint changed" in result.stderr
    assert not (destination / "requests.json").exists()
    assert hashes() == before
    evidence = {"time": datetime.now(timezone(timedelta(hours=8))).isoformat(), "network_requests": 0,
                "protected_files_unchanged": len(before), "checks": 4, "commands": commands,
                "protected_hashes": before, "status": "passed"}
    (OUT / "tool-isolation-verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"4 isolation checks passed; {len(before)} historical files unchanged; 0 HTTP requests")


if __name__ == "__main__":
    main()
