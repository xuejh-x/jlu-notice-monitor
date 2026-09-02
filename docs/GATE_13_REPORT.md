# Gate 13 Result

PASS — PRODUCTION DEPLOYMENT AND REAL JLU OA DEFERRED

## Architecture

- Official and shared Cloud sources execute once on Cloud; personal public and private sources execute locally.
- Stable `source_identity` canonicalizes the source URL and hashes it; `cloud_source_id` records the Cloud registry identity without changing the local database row ID.
- `cloud_policy` is `auto`, `force_enabled`, or `force_disabled`. Manual forced states always win. `auto` is only an interface for a future promotion policy, not a new recommendation system.
- Administrator mutations use a single server-configured key and remain separate from public feed GET APIs. No account or RBAC system was added.
- Private credentials, sessions, subscriptions and personal state stay on the Desktop side of the boundary.

## Gate 12.5 Delivered

- Sources-page **上云** action gated by successful Test/Preview.
- Password-style one-shot administrator-key dialog; input clears on both success and failure and is never persisted.
- Minimal Cloud Registry admin endpoints for promotion and policy changes.
- Identity-based create-or-reuse behavior for duplicate promotion.
- In-place Local-to-Cloud mapping that switches Desktop execution to the source-scoped Cloud feed and stops local duplicate crawling.
- Public registry reconciliation with locally disabled-by-default subscriptions for shared sources discovered on other devices.
- Safe **移出云端** (`force_disabled`) and **恢复自动** (`auto`) controls; historical rows remain identifiable and are not deleted.
- Optional 15-minute-minimum crawl interval metadata and scheduled-run enforcement.
- Source-level SSRF protection across initial URL, DNS results, every redirect, parsed links/attachments, and connected peer when exposed.
- `resolve_cloud_execution()` prevents future automatic policy from overriding manual decisions.

## Generic Connector Delivered

- Reused Gate 12 DPAPI credential boundary, private ownership, re-login UX, per-source profile paths and health states.
- Generic authenticated HTTP sources now convert HTTP 401/403 and configured-login redirects into `AUTH_SESSION_EXPIRED`, causing the crawler to pause with `needs_reauth` instead of retrying forever or reporting success.
- Authenticated HTML attachment metadata (`filename`, `url`, `type`) and expired-request behavior are covered by deterministic MOCK/FIXTURE tests.
- Redirect safety and connected-peer validation strengthen both public and private generic fetchers.
- No real OA behavior or unverified site adapter was added.

## Personal Data Boundary

- Cloud notices: shared facts.
- Subscriptions: local per device.
- Favorites: local per device.
- Read state: local per device.
- Importance rules: local per device.
- Private credentials/session state: local per device, never uploaded.

## Security

- Cloud key is read from `NOTICE_HUB_ADMIN_KEY`; `.env.example` contains only an empty setting.
- Constant-time comparison, explicit 401/403/503 behavior, failed-auth rate limiting, strict DTOs and 64 KiB request cap are implemented.
- Desktop requires HTTPS for the configured Cloud admin target; HTTP is permitted only for loopback development/test fixtures.
- Admin keys, passwords, cookies, Authorization headers, credential references and secret-like structured fields are redacted from validation/log output.
- SSRF tests cover localhost, private IPv4, IPv6 loopback/private, link-local metadata, non-HTTP schemes and redirect-to-private.
- Private-source secrets and browser/profile state remain excluded from Cloud, Git and installer inputs.

## Tests

- Backend: **97 passed** (`75` Gate 12 baseline + `22` Gate 13 tests).
- Frontend: **27 files / 135 tests passed**.
- Lint: **PASS**.
- TypeScript/Vite build: **PASS**, 2,795 modules transformed.
- Rust `cargo fmt --check`: **PASS**.
- Rust `cargo check`: **PASS**.
- Rust `cargo clippy -- -D warnings`: **PASS**.
- Rust `cargo test`: **4 passed**.
- Playwright: **13 passed**, including four MOCK/FIXTURE promotion journeys and the existing 390px smoke.
- Browser visual QA: **PASS** at 1440×900 and 390×844; the Sources page and administrator dialog had no horizontal overflow.

## Installer

- Version: `0.5.0`.
- Path: `E:\jlu-notice-monitor\frontend\src-tauri\target\release\bundle\nsis\JLU Notice Monitor_0.5.0_x64-setup.exe`.
- Size: `26,079,362` bytes.
- SHA-256: `98E3A24B7B7B9B06A7B67006867662D434203154E5D81082C42DD7A13F5BBA6E`.
- Fresh silent install into an isolated repository test directory: **PASS**.
- Installed launch and loopback health: **PASS**, version `0.5.0`, database initialized, scheduler running.
- Installed source-management API smoke: **PASS**, Gate 13 fields present.
- App exit: **PASS**, zero remaining packaged sidecars.
- Silent uninstall: **PASS**; isolated install directory removed. Isolated runtime data was then explicitly removed.

## Migration

Gate 12 → Gate 13: **PASS**. Migration `13.0` is idempotent and additive. It preserves source/notice IDs, source relations, attachments, read state, favorites, subscriptions, importance rules, custom/private sources, credential metadata and settings.

## Source Promotion Validation

Local → Cloud → restart → Cloud-feed execution → notice dedupe → favorite/read preservation: **PASS** in Backend and Playwright MOCK/FIXTURE coverage. Promotion updates the original local source row; canonical notice/public-ID dedupe then attaches Cloud facts without recreating user state.

## Production Protection

- production server accessed: **NO**
- production deployment: **NO**
- production DB changed: **NO**
- production env changed: **NO**
- Gate 10D soak modified: **NO**

**PRODUCTION DEPLOYMENT DEFERRED UNTIL GATE 10D ACCEPTANCE**

## Deferred

- Real JLU OA integration.
- Real JLU OA login.
- Real JLU OA DOM selectors.
- Real OA attachments.
- Real OA session expiry.
- Campus-network validation.
- Packaged arbitrary interactive-browser authentication/profile capture for sources that cannot use the supported Basic/Bearer/API-token/Cookie foundation.
- Production deployment until Gate 10D acceptance.

## Git

- commit: the Gate 13 commit containing this report; its immutable hash is recorded in the final handoff.
- branch: `master`.
- working tree: clean after the local Gate 13 commit.
- pushed: **NO**.

## Recommendation for Gate 14

Gate 14 may begin after Gate 10D-sensitive deployment work remains excluded. The listed real-OA and production items do not block local Gate 14 product development; they do block claims about production Cloud availability or real OA support.
