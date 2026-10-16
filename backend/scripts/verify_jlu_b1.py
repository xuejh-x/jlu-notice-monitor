"""Run JLU batch checks from an isolated source copy; never use the real database."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b0-b1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", choices=["baseline", "final", "targeted"])
    parser.add_argument("--batch", choices=["b0-b1", "b2", "b3", "b4", "b5-a", "b5-b", "b5-c", "b5-d", "b6", "b7", "r1-r2"], default="b0-b1")
    args = parser.parse_args()
    global OUT
    OUT = ROOT / "docs" / f"jlu-fix-{args.batch}"
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")
    isolated = ROOT / "backend/build" / f"jlu-{args.batch}-{args.label}-{stamp}" / "backend"
    assert isolated.resolve().is_relative_to((ROOT / "backend/build").resolve())
    isolated.mkdir(parents=True, exist_ok=False)
    files = {}
    for directory in ["app", "config", "tests", "alembic", "scripts"]:
        source = ROOT / "backend" / directory
        shutil.copytree(source, isolated / directory, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.key"))
        for file in source.rglob("*"):
            if file.is_file() and "__pycache__" not in file.parts:
                copied = isolated / directory / file.relative_to(source)
                if not copied.is_file():
                    continue
                files[file.relative_to(ROOT).as_posix()] = hashlib.sha256(copied.read_bytes()).hexdigest()
    for name in ["pyproject.toml", "alembic.ini"]:
        shutil.copy2(ROOT / "backend" / name, isolated / name)
    (isolated / ".env").write_text("JLU_DATABASE_URL=sqlite://\n", encoding="utf-8")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("JLU_", "NOTICE_HUB_")) and key not in {"PYTHONPATH", "TEST_POSTGRES_URL"}}
    env["PYTHONIOENCODING"] = "utf-8"
    # Fail closed before pytest imports database-owning modules.
    guard = "from pathlib import Path; import app; from app.config import get_settings; " \
            "assert Path(app.__file__).resolve().is_relative_to(Path.cwd()); " \
            "assert get_settings().effective_database_url == 'sqlite://'; print('isolated source + memory DB verified')"
    subprocess.run([sys.executable, "-c", guard], cwd=isolated, env=env, check=True)
    manifest = {"time": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "label": args.label, "isolated_backend": str(isolated), "database": "sqlite://",
                "source_hashes": files, "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (OUT / f"{args.label}-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--basetemp", str(isolated.parent / "pytest-tmp")]
    if args.batch == "r1-r2":
        command.extend(["--junitxml", str(OUT / f"{args.label}-junit.xml")])
    if args.label == "targeted":
        if args.batch == "r1-r2":
            command.extend(["tests/test_detail_refresh.py", "tests/test_crawler_orchestration.py",
                            "tests/test_database_dedup.py", "tests/test_gate13_hotfix.py",
                            "tests/test_gate14.py", "tests/test_retention.py", "tests/test_retention_ingestion.py",
                            "tests/test_phase15_cloud.py", "tests/test_stage17_2.py"])
        command.extend(["tests/test_jlu_b1.py", "tests/test_parser.py", "tests/test_gate12.py", "tests/test_gate13.py",
                        "tests/test_source_http_diagnostics.py", "tests/test_tls.py", "tests/test_oa.py"])
        if args.batch in {"b2", "b3", "b4", "b5-a", "b5-b", "b5-c", "b5-d", "b6", "b7"}:
            command.append("tests/test_jlu_b2.py")
        if args.batch in {"b3", "b4", "b5-a", "b5-b", "b5-c", "b5-d", "b6", "b7"}:
            command.append("tests/test_jlu_b3.py")
        if args.batch in {"b4", "b5-a", "b5-b", "b5-c", "b5-d", "b6", "b7"}:
            command.append("tests/test_jlu_b4.py")
        if args.batch in {"b5-a", "b5-b", "b5-c", "b5-d", "b6", "b7"}:
            command.append("tests/test_jlu_b5_a.py")
        if args.batch in {"b5-b", "b5-c", "b5-d", "b6", "b7"}:
            command.append("tests/test_jlu_b5_b.py")
        if args.batch in {"b5-c", "b5-d", "b6", "b7"}:
            command.extend(["tests/test_jlu_b5_c.py", "tests/test_crawler_orchestration.py", "tests/test_database_dedup.py"])
        if args.batch in {"b5-d", "b6", "b7"}:
            command.extend(["tests/test_jlu_b5_d.py", "tests/test_gate13_hotfix.py", "tests/test_gate14.py"])
        if args.batch in {"b6", "b7"}:
            command.append("tests/test_jlu_b6.py")
        if args.batch == "b7" and (isolated / "tests/test_jlu_b7.py").exists():
            command.append("tests/test_jlu_b7.py")
    with (OUT / f"{args.label}-tests.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, cwd=isolated, env=env, stdout=log, stderr=subprocess.STDOUT)
    print((OUT / f"{args.label}-tests.log").read_text(encoding="utf-8")[-5000:])
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
