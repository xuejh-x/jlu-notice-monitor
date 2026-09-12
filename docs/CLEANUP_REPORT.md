# Stage 16 Preparation — Cleanup Report

Date: 2026-09-12

Result: **PASS WITH DEFERRED USER-DATA REVIEW**

Scope: environment and generated-artifact cleanup only. Backend source, Frontend source, database schema, notification behavior, and source behavior were not changed.

## Deleted

### Installed application

- Located `C:\Users\zc\AppData\Local\Programs\JLU Notice Monitor`.
- Verified the installed executable metadata before removal:
  - Product: `JLU Notice Monitor`
  - Product/File version: `0.3.0`
  - Bundled uninstaller: `uninstall.exe`
  - Uninstaller SHA256: `89EB36240DD7A64790CB9249E102D70B3FBB279AF3D29868FE89FB90B3F28067`
- Ran the bundled NSIS uninstaller in silent mode. Exit code: `0`.
- Verified that the old installation directory no longer exists.
- No matching uninstall registry entry or running JLU Notice Monitor process remained.

### Project build artifacts

- `frontend/src-tauri/target/` — Cargo clean removed 17,809 files and reported 16.4 GiB reclaimed. This included:
  - debug and release executables;
  - release bundles;
  - NSIS installers for versions 0.3.0, 0.4.0, 0.5.0, and 0.6.0;
  - Rust build/dependency caches.
- `backend/build/` — old PyInstaller working files.
- `backend/dist/` — old packaged backend executable.
- `frontend/dist/` — generated Vite output.
- `frontend/.e2e/` — isolated E2E runtimes and old Gate 11/12 installed-app fixtures.
- `frontend/playwright-report/` and `frontend/test-results/`.
- `frontend/src-tauri/binaries/` — generated sidecar staging executable.
- `backend/.pytest_cache/`.
- Twelve project `__pycache__` directories outside `backend/.venv`.

The recorded cleanup reclaimed approximately **16.59 GiB**. A fresh Release Build will regenerate only the required outputs.

### Disposable application files

- `C:\Users\zc\AppData\Local\JLU Notice Monitor\cache\crawler_status.json`.
- `C:\Users\zc\AppData\Local\JLU Notice Monitor\logs\app.log`.

Both files were verified absent after deletion. Their parent directories were retained for the next application launch.

## Preserved

### Current user data

- `C:\Users\zc\AppData\Local\JLU Notice Monitor\data\notices.db` — 540,672 bytes.
- `C:\Users\zc\AppData\Local\JLU Notice Monitor\backups\notices-pre-gate15-20260911T213530.db` — 405,504 bytes.
- `C:\Users\zc\AppData\Local\JLU Notice Monitor\config\`.
- `C:\Users\zc\AppData\Local\JLU Notice Monitor\credentials\`.
- `C:\Users\zc\AppData\Local\com.jlunoticemonitor.desktop\` — matches the current Tauri identifier `com.jlunoticemonitor.desktop` and may contain current WebView/local settings.

### Repository inputs and dependencies

- All source code, configuration, documentation, tests, icons, manifests, Cargo metadata, and build scripts.
- `frontend/node_modules/`.
- `backend/.venv/`.
- `backend/jlu_notice_backend.spec` and other release-build configuration.
- The pre-existing dirty working tree was not reset, cleaned, or reorganized.

## Deferred — Not Deleted

The following directories look obsolete but may contain user session/state data. In accordance with the instruction to list uncertain data instead of deleting it, they were left untouched:

- `C:\Users\zc\AppData\Local\JLU Notice Monitor\oa-profile\` — approximately 159.9 MB. It is associated with the previous authenticated OA browser-profile implementation, but contains browser/session material.
- `C:\Users\zc\AppData\Local\com.jlunoticemonitor.app\` — approximately 93.9 MB. It uses an older Tauri identifier and contains WebView data.

These can be removed later only after explicit confirmation that no OA session or legacy WebView settings need to be retained.

## Risk Checks

- Deletion targets were resolved to exact absolute paths before recursive project cleanup.
- Only paths belonging to JLU Notice Monitor or generated files inside this repository were selected.
- The unsigned NSIS uninstaller was run only after its product name, version, location, and hash were recorded.
- The installer hook confirms application binaries and runtime data use separate directories, so uninstalling `Programs\JLU Notice Monitor` did not remove the current database directory.
- No other application registry entries, directories, shortcuts, processes, or user data were modified.
- The cleanup did not invoke a new build or test run after artifact removal, because that would recreate the caches being removed.

## Current Environment State

- Windows installed-app registry entries matching `JLU Notice Monitor`: **0**.
- Desktop shortcuts matching `JLU Notice Monitor`: **0**.
- User/Common Start Menu shortcuts matching `JLU Notice Monitor`: **0**.
- Common installation directories matching `JLU Notice Monitor`: **0**.
- Remaining project `.exe`, `.msi`, `.dmg`, `.appimage`, `.deb`, or `.rpm` artifacts outside preserved dependencies/venv: **0**.
- `frontend/src-tauri/target/`: absent.
- PyInstaller, sidecar staging, Vite, E2E, and Playwright output directories: absent.
- Current database and Gate 15 pre-migration backup: present.
- Current WebView data, `node_modules`, and Python venv: present.

The workspace is ready for a clean Release Build. The two deferred user-data directories do not affect build reproducibility, but should be resolved before claiming a complete removal of all legacy per-user state.
