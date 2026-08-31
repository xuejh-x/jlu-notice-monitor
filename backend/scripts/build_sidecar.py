from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPOSITORY_DIR = BACKEND_DIR.parent
SPEC_PATH = BACKEND_DIR / "jlu_notice_backend.spec"
DIST_EXECUTABLE = BACKEND_DIR / "dist" / "jlu-notice-backend.exe"
TAURI_BINARIES_DIR = REPOSITORY_DIR / "frontend" / "src-tauri" / "binaries"


def get_host_triple() -> str:
    result = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise RuntimeError("rustc did not return a host tuple")
    return value


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Gate 8A backend sidecar packaging currently targets Windows only")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_PATH)],
        cwd=BACKEND_DIR,
        check=True,
    )
    if not DIST_EXECUTABLE.is_file():
        raise FileNotFoundError(f"PyInstaller output missing: {DIST_EXECUTABLE}")
    target = TAURI_BINARIES_DIR / f"jlu-notice-backend-{get_host_triple()}.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DIST_EXECUTABLE, target)
    print(f"Staged Tauri sidecar: {target}")


if __name__ == "__main__":
    main()
