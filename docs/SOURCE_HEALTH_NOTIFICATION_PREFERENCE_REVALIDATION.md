# Source Health / Notification Preference Revalidation

Date: 2026-09-12

Result: **PASS**

Scope: revalidate the existing Gate 14 source-health and notification-preference implementation against the current OA/public-source and Cloud-source working tree. No application code change was required by this revalidation.

## Architecture

- `Source.health_state`, `last_error_code`, and the previous health state are the shared source-health inputs. The crawler records an event only when a source crosses a meaningful health-state boundary.
- `record_source_health_transition` is source-neutral. OA, built-in public sources, local sources, and Cloud-backed sources enter the same transition classifier; no OA-only health or notification path is present.
- `NotificationPreference` is a singleton, device-local SQLite row. It does not reuse notice read/favorite state and is not synchronized to Cloud.
- `NotificationEvent` owns semantic deduplication and reminder read state. `NotificationDelivery` owns the Windows delivery state machine.
- `NotificationScheduler` is a local, no-backlog clock for deadline and daily-summary generation. It starts and shuts down in the FastAPI lifespan alongside, but independently from, the crawler scheduler.
- Cloud remains the shared notice plane. Cloud-role notification generation and notification APIs remain disabled, and the existing Cloud Source resolution/promotion logic is retained.

## API

All routes are under `/api/notifications` and are available only for local/Desktop roles:

- `GET /preferences` — read the device-local preference singleton.
- `PATCH /preferences` — validate and replace the preference values, suppress disabled deliveries, and generate newly eligible scheduled events.
- `GET /` — list recent notification events and the notification-specific unread count.
- `POST /generate` — run one idempotent scheduled-event generation pass.
- `POST /claim` — durably claim one eligible Windows delivery.
- `POST /deliveries/{delivery_id}/ack` — acknowledge a claim as `DELIVERED` or `FAILED`.
- `POST /{event_id}/read` — mark only the reminder event as read.

Source-health configuration continues to use the existing source-management DTO/API. No OA-specific health endpoint was added.

## Stability Evidence

- Scheduler: the E2E backend started the crawler scheduler through the real FastAPI lifespan; backend scheduler lifecycle and no-backlog tests passed. The notification scheduler lifecycle and Gate 14 generation tests are included in the full backend pass.
- Existing sources and Cloud logic: the full backend suite passed, including crawler orchestration, source management, public feed, Cloud isolation, and source-transition coverage.
- OA: backend OA fixtures passed and the E2E journey confirmed that OA 校内通知 is exposed as an official public subscription without login UI.
- Existing notification state machine: unchanged. Revalidation exercised the committed Gate 14 delivery implementation without rewriting its states or migration.

## Test Results

Commands were run from the current working tree on 2026-09-12:

- Backend: `129 passed in 4.63s`.
- Frontend unit/component: `28` files, `169 passed`.
- Frontend lint: PASS.
- Frontend TypeScript + Vite production build: PASS.
- Playwright E2E: `24 passed in 34.0s`.

The E2E run used isolated loopback fixture services. It covered startup refresh, OA public subscription, Cloud HTML configuration, source promotion/mapping, desktop and 390 px navigation, Bell-to-detail routing, notification dedupe, deadline generation, daily summary contents, and preference persistence.

## Known Limitations

- Native delivery is Desktop/Windows only. Mobile, Web Push, and email delivery remain out of scope.
- Browser E2E validates the local API/UI bridge but does not prove a human-visible Windows Action Center toast on every host configuration.
- SQLite and Windows do not share a transaction. The guarantee remains persistent semantic dedupe with at-most-once native enqueue and best-effort delivery; stale ambiguous claims become `UNCERTAIN` instead of being resent automatically.
- Source recovery to `healthy` does not currently produce a recovery notification.
- Notification preferences and reminder read state are intentionally device-local and do not follow a user across devices.
- The production bundle still reports the existing non-blocking Vite warning for a JavaScript chunk larger than 500 kB.

## Boundary Check

This revalidation introduced no new database system, did not modify the notification delivery state machine, did not remove Cloud Source behavior, did not add OA-specific health/notification code, and did not change the frontend framework.
