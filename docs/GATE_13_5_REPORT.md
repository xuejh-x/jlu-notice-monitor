# Gate 13.5 Result — Cloud Shared Source + Notification State

Status: PASS

## Cloud Shared Source

- Added authenticated Cloud Registry CRUD at `POST/GET /api/cloud/sources` and `PATCH/DELETE /api/cloud/sources/{id}` while preserving the Gate 13 compatibility routes.
- Reused the existing `Source` entity as the Cloud registry row. Stable `source_identity`, `cloud_source_id`, `source_scope`, `execution`, and `cloud_policy` remain authoritative.
- Added the Desktop-side `POST /api/source-config/cloud-sources` orchestration endpoint. It consumes a successful preview token, forwards the one-shot administrator key through the existing HTTPS Cloud boundary, then creates or updates the local source mapping in place.
- A successfully created shared source is locally subscribed and uses `execution=cloud`; Desktop resolves it to `CloudFeedSource`, so the original HTML/RSS/API adapter does not crawl it again.
- Added generic JSON API source parsing. Common `items/results/data/notices` arrays are supported, with the existing selector fields usable as dot-path mappings.
- Cloud deletes are soft deletes. The public registry excludes deleted rows and Desktop reconciliation disables a shared source that disappears from the registry.

## Notification state fixes

- Fixed the mark-unread race: a deliberate unread transition is registered before the automatic-read effect can observe it.
- Read mutations now optimistically update detail, all notice lists, search results, Dashboard recent notices, and the unread counter. Error rollback and server invalidation remain in place.
- Added `dashboard.total_count`; the Sidebar and the “全部” tab use it instead of the active filtered list total.
- Corrected unread aggregation so notices without a `UserState` row are counted as unread, matching serialization and the unread list filter.
- Important and deadline counts remain independent and unchanged by read-state transitions.

## Database

No schema migration and no duplicate model were added. Existing Gate 13 additive source columns and `Source` rows are reused.

## Configuration

Administrator authentication continues to use `NOTICE_HUB_ADMIN_KEY`; the key is not embedded in business code, frontend bundles, SQLite, or localStorage. Desktop Cloud forwarding continues to use `NOTICE_HUB_CLOUD_ADMIN_URL`.

## Verification

- Backend pytest: 129 passed.
- Frontend Vitest: 28 files / 168 tests passed.
- Frontend lint: PASS.
- Frontend TypeScript/Vite build: PASS (2,804 modules transformed; existing chunk-size warning only).
- Playwright: 23 passed, including direct Cloud creation, one-click mark-unread, independent total count, and 390px no-overflow coverage.
