# JLU Notice Monitor

English | [中文](README_zh-CN.md)

> A Windows desktop app that aggregates, deduplicates, filters, and delivers notices from official campus sources.

## Current stable release: v0.7.0-rc3

- [Release notes and downloads](https://github.com/xuejh-x/jlu-notice-monitor/releases/tag/v0.7.0-rc3)
- [Windows x64 installer](https://github.com/xuejh-x/jlu-notice-monitor/releases/download/v0.7.0-rc3/JLU.Notice.Monitor_0.7.0-rc3_x64-setup.exe)
- [SHA256SUMS](https://github.com/xuejh-x/jlu-notice-monitor/releases/download/v0.7.0-rc3/SHA256SUMS.txt)

The currently distributed desktop package is for Windows x64.

JLU Notice Monitor helps students follow important announcements without repeatedly checking separate university and department websites. It currently ships with Jilin University sources, while its source-adapter model is designed to support other public organizations and campuses.

![JLU Notice Monitor desktop interface](docs/design/ui-v2-stage3.3/after-1440x900.png)

## Features

- Aggregates notices from multiple official sources.
- Performs incremental crawling, content-hash deduplication, and update detection.
- Extracts notice content, attachments, categories, importance, and deadlines.
- Supports search, source/category filters, pagination, read state, favorites, and responsive layouts.
- Keeps per-device read/unread state, including confirmed, idempotent **mark all read**.
- Uses Cloud Feed synchronization for cloud-enabled sources, with safe local fallback for eligible official public sources when a cloud feed is unavailable or stale.
- Sends Windows native notifications according to local importance, deadline, quiet-hours, and source-health preferences.
- Stores the local database and preferences in the user's application-data directory; upgrades do not replace that data.

## Supported sources

The bundled v0.7.0-rc3 adapters cover:

- Jilin University OA public campus notices
- School of Cyber Science and Engineering
- College of Computer Science and Technology
- College of Software
- Undergraduate School
- College of Innovation and Entrepreneurship

Additional public or local sources can be added through the source-management architecture. A source shown above can still be temporarily unavailable when its upstream website is offline or changes its markup.

## Architecture

```text
Official source / cloud feed
            |
     Source adapters
            |
 FastAPI processing pipeline
  crawl -> parse -> deduplicate
       -> classify -> notify
            |
        SQLite data
            |
 React + TypeScript interface
            |
   Tauri 2 Windows desktop app
```

The production installer bundles the Tauri application and a managed FastAPI backend sidecar. The sidecar binds only to a dynamically allocated loopback port. Source code, Python environments, Node modules, development tools, databases, and logs are not part of the installer.

## Technology stack

- Frontend: React and TypeScript
- Backend: FastAPI
- Desktop: Tauri 2
- Local data: SQLite
- Cloud deployment support: PostgreSQL configuration and Alembic migrations

PostgreSQL support is included for Cloud deployment, but a production Cloud deployment is not represented as verified by this release.

## Install on Windows

1. Open the [v0.7.0-rc3 GitHub Release](https://github.com/xuejh-x/jlu-notice-monitor/releases/tag/v0.7.0-rc3).
2. Download the [Windows x64 installer](https://github.com/xuejh-x/jlu-notice-monitor/releases/download/v0.7.0-rc3/JLU.Notice.Monitor_0.7.0-rc3_x64-setup.exe) and [SHA256SUMS](https://github.com/xuejh-x/jlu-notice-monitor/releases/download/v0.7.0-rc3/SHA256SUMS.txt).
3. Verify the checksum in PowerShell:

   ```powershell
   Get-FileHash -Algorithm SHA256 '.\JLU.Notice.Monitor_0.7.0-rc3_x64-setup.exe'
   ```

4. Run the installer and launch **JLU Notice Monitor** from the Start menu or shortcut.
5. On first use, let the application complete its configured source synchronization. Use the in-app source and notification settings to control available notification features.

Windows 10/11 x64 and Microsoft Edge WebView2 Runtime are required. Supported Windows versions normally include WebView2; if it is missing, install the current runtime from Microsoft before launching the app.

Before upgrading an existing installation, back up important local data. The local database is stored at `%LOCALAPPDATA%\JLU Notice Monitor\data\notices.db`; do not delete it as an upgrade workaround.

## Cloud synchronization

Cloud-enabled sources can publish a feed that the desktop client synchronizes into its local SQLite database. First successful Cloud synchronization establishes a local baseline, so existing historical notices are not presented as new or unread. Later genuinely new notices retain the normal NEW / UPDATED / UNCHANGED behavior.

The Cloud data model, PostgreSQL deployment configuration, and migrations are part of the repository. A production Cloud service chain has not yet been independently verified; the desktop client retains its implemented local fallback behavior where that policy is applicable.

## Release notes and known limitations

v0.7.0-rc3 passed the recorded automated regression suites and installer integrity verification. The following real-environment checks remain incomplete:

- Windows clean-install and prior-version upgrade acceptance have not been fully exercised on an isolated machine.
- PostgreSQL live-instance testing and production Cloud-chain verification have not been completed.
- Existing databases with historical NEW/unread false positives are intentionally not cleaned automatically, because those records cannot be safely distinguished from genuine notifications.

Please report issues through the repository's GitHub Issues page.

## Development

Prerequisites:

- Python 3.12 or newer (the project CI and release environment use Python 3.13)
- Node.js 24 and npm
- Rust toolchain compatible with Rust 1.77.2 or newer
- Windows and NSIS prerequisites for packaging the desktop installer

Set up the backend:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,desktop]'
.\.venv\Scripts\python.exe -m pytest
```

Set up and validate the frontend:

```powershell
Set-Location frontend
npm ci
npm test -- --run
npm run lint
npm run build
npm run e2e
```

Build the production Windows installer:

```powershell
Set-Location frontend
npm run desktop:build
```

The build script first produces the PyInstaller backend sidecar, then builds the frontend and Tauri NSIS package. Local configuration belongs in the provided `.env.example` files; never commit credentials or runtime data.

## Repository layout

- `backend/` — FastAPI application, crawler, SQLite models, and pytest suite
- `frontend/` — React/Vite interface, Vitest and Playwright tests, and the Tauri shell
- `docs/` — design contract, implementation reports, and validation evidence

## License

No project-wide open-source license has been declared yet. Source availability does not grant permission to redistribute or create derivative works. Third-party assets retain the licenses documented alongside them.
