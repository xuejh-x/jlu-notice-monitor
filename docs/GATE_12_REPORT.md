# Gate 12 Result

**PASS — PRODUCTION CLOUD DEPLOYMENT PENDING GATE 10D**

Gate 12 repository implementation, local security review, regression suites, and isolated Windows installed-app QA are complete. The Gate 10D production server was not contacted or modified. Consequently, the Cloud-first contract is verified locally but not yet verified against the production deployment.

## Baseline

- Starting commit: `db70479d847c7268f0af793bba36d5cfda1e1fd8`
- Branch: `master`
- Starting working tree: clean
- Starting versions: Desktop/frontend `0.3.0`; backend API `0.2.0`
- Starting regression baseline: backend 62 tests; frontend 123 tests; Rust 4 tests
- Architecture facts and pre-change constraints are recorded separately in `docs/GATE_12_ARCHITECTURE_AUDIT.md`.

## Architecture

### Before

- Every Desktop could crawl the built-in public university sites itself.
- Source definitions primarily came from `backend/config/sources.yaml`; OA was a special-case source.
- Importance keyword weights primarily came from `backend/config/keywords.yaml` and were not user-local editable records.
- The scheduler ran periodically, but a Desktop launch did not own an exactly-once immediate check.

### After

- Sources explicitly carry ownership: `OFFICIAL_CLOUD`, `CUSTOM_LOCAL_PUBLIC`, or `CUSTOM_LOCAL_PRIVATE`.
- The cloud deployment role crawls official adapters. The Desktop production role imports official notices through a versioned public feed. Standalone/development mode retains the existing direct-adapter workflow for local development.
- Public factual notice data and local personal state are separate. Read, favorite, source subscription, local source configuration, credentials, profiles, and importance rules remain local.
- Custom public and private sources are database-backed and managed by local APIs. Built-in YAML is retained as seed/default adapter metadata rather than the only source registry.
- Existing OA code is represented as a private browser-session source while its real logged-in DOM integration remains deferred.

### Cloud/local responsibility boundary

| Concern | Notice Hub cloud | Desktop installation |
| --- | --- | --- |
| Official source crawling | Yes | No in Desktop production role |
| Official factual notice feed | Read-only producer | Incremental consumer/cache |
| Read/favorite state | Never authoritative or exported | Local SQLite |
| Personal importance | Not exported | Locally computed |
| Official subscriptions | Not user-specific | Local preference |
| Custom public sources | No | Local crawler/configuration |
| Private sources/credentials/profiles | Never uploaded | Local only |

## Desktop Startup Sync

- FastAPI lifespan invokes a process-local `StartupSyncCoordinator` once after database/source initialization and before normal scheduler operation.
- Startup uses the same crawler manager, asyncio lock, and process lock file as manual/scheduled checks. An already-running crawler produces a safe `skipped_running` outcome instead of a duplicate run.
- React never initiates startup crawling. It observes crawler status, renders `正在检查最新通知…`, polls while the startup run is active, and invalidates notices/dashboard/search/source queries when it finishes.
- The UI remains usable during the background run. A source or cloud failure updates health/status but does not delete cached notices.
- Final installed-app QA launched the app twice. Each launch reported `trigger_source=startup`; no sidecar remained two seconds after each app exit.

## Official Public Sources

- New GET-only contract: `/api/public/v1/sources` and `/api/public/v1/notices`.
- Notice payloads contain stable SHA-256 public identity, source identity, title/content/URLs, dates, category, attachment metadata, content hash, and updated timestamp.
- Payloads intentionally omit importance score, read/favorite state, credentials, profile/runtime paths, source health, errors, and private configuration.
- Pagination is capped at 100 records and supports incremental `(updated_after, after_id)` cursors. A process-local 120 requests/minute/IP limiter provides basic abuse control.
- Desktop `CloudFeedSource` imports normalized candidates, maintains incremental cursors in local app state, and lets the existing persistence path preserve personal state.
- Cloud failure is surfaced as source health failure while existing cache remains. The Desktop does not fall back to crawling all official sites.
- Official subscription switches only filter/suppress that Desktop's cached official content and feed work. They never disable the cloud crawler or delete local notice rows.
- No production feed URL is embedded in the installer. `JLU_PUBLIC_FEED_URL` remains a deployment setting pending Gate 10D acceptance.

## Custom Public Sources

- Local CRUD supports add, edit, enable, disable, check, soft delete, health/error state, and last successful fetch.
- RSS 2.0 and Atom feeds are auto-detected from content type/body, or can be selected explicitly.
- Generic static HTML uses the existing safe list/detail parsers. Advanced configuration supports item, title, link, date, detail content, attachment, next-page selectors, and a pagination limit.
- Source/parser creation and parser-changing edits require a matching, one-time, ten-minute preview token. Failed/empty/unsupported previews do not persist a source.
- Preview returns at most three detail samples and clearly reports unsupported structures; the UI explicitly avoids claiming universal website compatibility.
- Limits: HTTP(S) only, URL length 2,000, no URL credentials, maximum three redirects, 5 MB response cap, maximum three configured pages, existing item cap, 120-second per-source run deadline, and at most 50 parsed attachments per detail.

## Private Source Framework

- Authentication model supports `username_password`, `browser_session`, `cookie`, `basic`, `bearer`, `api_token`, and `custom_adapter` in addition to `none` for public sources.
- Basic, Bearer/API-token, and Cookie sources load secrets from local DPAPI storage for scheduled HTTP requests; API responses expose only `password_saved` metadata.
- Each private source receives an independent `auth-profiles/<source-code>` reference. OA preserves its existing dedicated persistent `oa-profile` compatibility path.
- Health states distinguish `healthy`, `syncing`, `disabled`, `needs_reauth`, `auth_error`, `parse_error`, `network_error`, `unsupported`, and source errors.
- Expired/invalid authentication transitions to `needs_reauth`; the scheduler treats that source as disabled until repaired, while other sources continue. Scheduler evaluation does not open login UI or update notification timestamps every cycle.
- The Sources page persistently shows source-level and application-level re-login state. Re-login is explicitly user initiated.
- Enabling a private source requires acknowledgement of local storage, expiry behavior, and possible CAPTCHA/MFA/manual verification. CAPTCHA/MFA bypass is neither implemented nor claimed.
- Source deletion optionally clears its DPAPI secret and dedicated profile; transient fetch errors never clear either.

## Personal Importance

- `importance_rules` stores local keyword, signed weight, enabled state, and system-default provenance in SQLite under app data.
- First initialization copies system defaults from `keywords.yaml`; later installer launches do not overwrite user rules.
- Allowed weight range is `-50..50`; the UI warns when one keyword exceeds approximately `±35`.
- The scoring model retains base score, system category signal, and deadline urgency, then applies the enabled local keyword weights and clamps to the existing valid score range.
- Every create/update/delete/restore operation deterministically re-scores all existing local notices. User read/favorite rows are untouched, and frontend mutations invalidate notice/dashboard/search data.
- The Settings page supports keyword add/edit/delete, signed weight, enable/disable, restore confirmation, validation, and save feedback.
- The compact guidance tooltip appears on both mouse hover and keyboard focus and explains the recommended positive/negative ranges.

## Database / Migration

- Additive migration `12.0` adds source ownership/type/parser/subscription/auth/health/profile/soft-delete metadata, notice public identity, importance rules, app state, and schema-migration tracking.
- Migration is idempotent and backfills built-in official sources plus OA ownership without dropping or rebuilding existing notice/user tables.
- Automated migration starts from an old schema and verifies notice, read state, favorite state, IDs, source subscription, and repeated migration safety.
- Installed-app upgrade QA used an isolated 0.3.0-created database with a crawler-shaped notice/source relation and synthetic read/favorite marker. The final 0.4.0 app returned that notice through its API with both states preserved.
- No test used the real `%LOCALAPPDATA%\JLU Notice Monitor` database.

## Frontend

- Existing navigation and visual system were retained; no new route or UI redesign was introduced.
- Sources now groups official, local public, and local private sources, and contains preview/configuration, advanced selectors, enable warnings, health, delete choices, and re-login actions.
- Settings now contains the local personal-importance editor and accessible help tooltip.
- The existing header shows a compact persistent warning when any source needs reauthentication.
- Browser QA covered the Sources and Settings views at the default Desktop viewport and the existing 390 px regression layout. There were no console errors or horizontal overflow. No mobile feature work was added.

## Security

- Saved secrets use Windows DPAPI, scoped to the local Windows user, in separate `.dpapi` files. SQLite/API responses store only a validated opaque reference and non-secret metadata.
- Request validation errors strip raw secret-bearing input locations. Crawler logs use structured source/error codes and never log Authorization/Cookie header values.
- Source URLs reject non-HTTP(S) schemes, embedded credentials, loopback/private/link-local/multicast/reserved/unspecified addresses unless a private source explicitly opts into private-network access. Redirect targets and parsed notice/attachment URLs are revalidated.
- HTML is parsed server-side into text/metadata; raw custom HTML is not injected into React. Existing frontend rendering/CSP boundaries remain in place.
- Public-feed tests assert that read, favorite, score, private source state, and credentials are absent.
- Repository secret scan found only an intentional fake password in a test and a commented example feed domain. The PyInstaller spec packages backend code plus `config/` only; it does not include `.env`, databases, credentials, or browser profiles.

## Tests

Final commands and results:

- `backend\.venv\Scripts\python.exe -m pytest` — **75 passed**
- `npm test -- --run` — **27 files, 131 tests passed**
- `npm run lint` — **PASS**
- `npm run build` — **PASS**, 2,795 modules transformed
- `cargo fmt --check` — **PASS**
- `cargo check` — **PASS**
- `cargo clippy -- -D warnings` — **PASS**
- `cargo test` — **4 passed**
- `npm run e2e` — **9 passed**
- `npm run desktop:build` — **PASS**, sidecar + release app + NSIS bundle
- In-app browser visual/interaction QA — **PASS**, Desktop and 390 px regression viewport, tooltip keyboard focus, no console errors
- Isolated final NSIS install + two launches — **PASS**, API version `0.4.0`, startup trigger observed twice (once per launch), rule persisted across restart, zero remaining sidecars
- Isolated Gate 11 runtime upgrade — **PASS**, notice/read/favorite preserved

The initial concurrent lint/build attempt found one TypeScript-only test fixture field mismatch. The fixture was corrected, after which the complete frontend test/lint/build sequence passed and the final installer was rebuilt.

## Installer

- Product version: `0.4.0` across frontend package/lock, Tauri Cargo package/lock, Tauri config, and backend package/API
- Path: `E:\jlu-notice-monitor\frontend\src-tauri\target\release\bundle\nsis\JLU Notice Monitor_0.4.0_x64-setup.exe`
- Size: `26,064,472` bytes
- SHA-256: `851A1453641283413E97C395816562B6B32EC0C28E1FA2A09F58A73942EBEE7A`

## Gate 10D Protection

The Gate 10D production server was not accessed, modified, restarted, redeployed, or reconfigured. Nginx, Basic Auth, production databases, services, timers, soak scripts, and logs were untouched.

**Gate 12 cloud production deployment deferred until Gate 10D final acceptance.**

## Git

- Final local commit: recorded in the handoff after report commit
- Final working tree: expected clean after local commit
- Pushed: **no**

## Deferred to Gate 13

- Real JLU OA login, list/detail/attachment DOM verification on the actual authenticated site and campus/network conditions.
- Packaged visible browser-session capture and dedicated-profile login completion for arbitrary interactive sources. Gate 12 models per-source profiles and states, and retains the existing OA persistent-profile adapter, but the current installed sidecar intentionally excludes Playwright and re-login opens the configured system login URL; it does not claim that an arbitrary system-browser login populates the crawler profile.
- Site-specific, tested expiry detection and safe automatic reauthentication where saved credentials genuinely suffice.
- CAPTCHA, QR, SMS, TOTP, MFA, SSO, and mobile confirmation remain user-completed flows; they will not be bypassed.

## Remaining Risks

- Production Cloud-first behavior is unverified until the public feed is deployed/configured after Gate 10D. With no feed URL, the Desktop correctly reports `PUBLIC_FEED_NOT_CONFIGURED`, retains cache, and continues eligible local sources.
- DNS resolution is validated before each request and redirect, but the usual DNS-rebinding time-of-check/time-of-use gap remains because the HTTP client does not pin the validated IP.
- Public rate limiting is process-local and intended as simple abuse control, not distributed enforcement for a multi-instance deployment.
- Generic HTML auto-detection is intentionally conservative; JavaScript-only or structurally unusual sites may require selectors or remain unsupported.
- Interactive browser-session completion for generic private sources is framework-level in Gate 12 and requires the packaged workflow described under Gate 13 before production claims.
