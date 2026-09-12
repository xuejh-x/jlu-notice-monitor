# Gate 13.6 Result — OA Chrome Authentication + Cloud Source Compatibility

Status: PASS

## OA Chrome Authentication

- Replaced the Playwright browser launch path with a small Chrome DevTools Protocol client that launches the user's installed Google Chrome executable. No Playwright browser download or bundled Chromium runtime is required.
- Added explicit environment diagnostics for Chrome, Desktop Runtime, and the OA adapter. Errors are reported as stable codes such as `OA_CHROME_NOT_FOUND`, `OA_CHROME_START_FAILED`, `OA_CHROME_CDP_UNAVAILABLE`, and `OA_LOGIN_ADAPTER_UNAVAILABLE`.
- Split login into two user-driven actions: start Chrome login, then detect login status. CAPTCHA, SSO, MFA, QR, and VPN steps remain manual.
- Successful detection captures only OA-domain cookies. The existing Windows DPAPI credential store encrypts the serialized cookie set locally; SQLite stores only `credential_ref`. The local Chrome profile and encrypted credential file survive restart.
- OA remains `CUSTOM_LOCAL_PRIVATE`, `source_scope=private`, and `execution=local`. No credential, cookie, profile, or session value enters Cloud Registry or a frontend persistence store.

## Cloud Source Advanced HTML Selectors

- When automatic preview fails, Cloud Source creation now opens Advanced HTML configuration instead of ending the workflow.
- Added `parser_config.type=html_selector` plus `item_selector`, `title_selector`, `url_selector`, and `time_selector` support. Existing `link_selector` and `date_selector` remain compatible.
- The same `parse_configured_html` implementation is used by preview and Cloud Worker. When the initial response has no matching DOM (including an empty Vue/React mount point), the adapter uses installed Chrome in headless mode and waits for `item_selector` before parsing.
- Every HTTP(S) request observed during CDP rendering is paused and checked through the existing local/cloud URL safety policy before it is continued. Missing Chrome or selector timeouts remain explicit preview/worker failures.
- A matching successful preview token is still mandatory before Cloud Registry creation.
- Created sources retain the Gate 13 identity and execution path: Cloud Registry → `cloud_source_id` → `execution=cloud` → Cloud Worker; Desktop resolves the source to its cloud feed and does not crawl the original URL.

## API Changes

- `GET /api/source-config/{id}/authentication-environment` — reports Chrome/Desktop/OA-adapter readiness and whether a login session is active.
- `POST /api/source-config/{id}/reauthenticate` — now starts system Chrome and returns `chrome_login_opened` or `login_in_progress` for OA.
- `POST /api/source-config/{id}/authentication-status` — detects OA login completion, persists the encrypted local session, and returns `authenticated` or `not_authenticated` with a reason.
- Existing Cloud Source CRUD endpoints are unchanged. Their `parser_config` payload now accepts the HTML selector fields above.

## Database

No schema migration and no duplicate source model were added. Existing `Source.parser_config`, `Source.credential_ref`, source identity, Cloud policy, and execution columns are reused.

## Verification

- Backend pytest: 132 passed.
- Frontend Vitest: 28 files / 169 tests passed.
- Frontend lint: PASS.
- Frontend TypeScript/Vite build: PASS (existing chunk-size warning only).
- Production Backend sidecar build and executable smoke test: PASS; PyInstaller included the WebSocket/CDP client while Playwright remains excluded.
- Playwright E2E: 24 passed, including Chrome readiness/first-login/status detection, Cloud automatic-preview failure, advanced-selector retry, existing RSS/API Cloud creation, notification state, and 390px layout coverage.
- Local runtime preflight on the target Windows machine: Google Chrome found; Desktop Runtime and OA CDP adapter available.

## Gate Status

Gate 13.6 is complete. Gate 10–14 ownership, privacy, Cloud execution, notification state, URL, attachment, and auto-read contracts remain preserved.
