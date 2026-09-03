# Gate 14 Report — Notification Delivery & User Reminder System

Date: 2026-09-03

Result: **PASS**

Version: **0.6.0**

Baseline: `ece8527f01008a1a51c8568de7629370e1a95658`

## Architecture

Gate 14 separates shared notice content from local reminder behavior:

```text
Notice / Source / local-day aggregate
                |
                v
       NotificationEvent (unique semantic dedupe key + independent read state)
                |
                v
       NotificationDelivery (event + channel unique)
                |
                v
       local claim API -> Tauri bridge -> Windows toast
```

The persisted delivery states are `PENDING`, `SENDING`, `DELIVERED`, `FAILED`, `SUPPRESSED`, and `UNCERTAIN`. A delivery is committed as `SENDING` with a claim token before the Windows API is called. Native acceptance is acknowledged as `DELIVERED`; a definite rejection becomes `FAILED` and is eligible for a bounded retry (maximum three attempts with backoff). A stale `SENDING` claim becomes `UNCERTAIN` and is not automatically resent.

The exactly-once scope is intentionally precise: Gate 14 provides database-level semantic event uniqueness, one delivery row per event/channel, durable restart dedupe, and at-most-once native enqueue for ambiguous attempts. SQLite and Windows do not share a transaction, so end-to-end display cannot be mathematically exactly once. The implemented guarantee is **persistent semantic dedupe with at-most-once native enqueue and best-effort delivery**. It prefers a missed retry over a duplicate toast when the process dies after Windows accepts a notification but before acknowledgement is persisted.

The complete pre-implementation audit is in `docs/GATE_14_ARCHITECTURE_AUDIT.md`.

## Delivered

- Independent `NotificationEvent`, `NotificationDelivery`, and singleton `NotificationPreference` models.
- Unique keys for new/important notices, deadline lead buckets, deadline changes, source-health transitions, and one daily summary per local date.
- New/important arbitration: an important new notice produces one important alert rather than an additional generic alert.
- Local scheduler for 7/3/1-day deadline reminders and a once-per-local-day 09:00 summary.
- Daily summary counts for new, important, upcoming-deadline, and unread notices.
- Quiet hours with persisted `available_at`; events wait until the quiet period ends.
- Transition-only source-health notifications with `info` for unconfigured cloud feeds, `warning` for reauthentication, and `error` for genuine failures.
- Tauri notification capability, permission flow, bounded local delivery polling, and a Windows WinRT toast bridge.
- Notification activation focuses/restores the app and routes only to allow-listed internal pages, including `/notices/:id`.
- Bell popover with recent events, notification-specific unread state, click routing, and links to reminder settings/deadlines.
- Additive Settings controls for master enable, new, important, deadline, lead days, minimum score, daily summary, source health, and quiet hours.
- Notification read state remains separate from notice read state.

## Data Boundary

- Cloud remains the shared-notice plane.
- Notification events, delivery state, notification-read state, and preferences remain in Desktop SQLite.
- Cloud-role event generation is disabled, and cloud-role notification API access returns `404`.
- No account system was introduced. Favorites, notice read state, and reminder preferences are not uploaded or synchronized.

## Tests

- Backend: **113 passed** (`pytest`), including creation, semantic dedupe, deadline generation/change, daily-summary local-date uniqueness, restart persistence, definite-failure retry, stale-claim quarantine, preference filtering, quiet hours, migration preservation, source severity, and cloud-role isolation.
- Frontend: **28 files / 143 tests passed**; `oxlint` passed; TypeScript and Vite production build passed.
- Rust/Tauri: `cargo fmt --check`, `cargo check`, and clippy with warnings denied passed; **6 Rust tests passed**, including route and payload validation for the notification bridge.
- Playwright: **18/18 passed** — the existing 13 journeys plus Bell-to-detail, restart-style daily dedupe, deadline uniqueness, daily-summary contents, and preference persistence.
- Visual: local fixture UI checked in the in-app browser at desktop width and **390×844** mobile width; no responsive layout regression or horizontal overflow was observed.
- All integration and visual runs used local loopback services and isolated fixture data.

## Installer

- Artifact: `frontend/src-tauri/target/release/bundle/nsis/JLU Notice Monitor_0.6.0_x64-setup.exe`
- Version: **0.6.0**
- Size: **45,410,998 bytes (43.31 MiB)**
- SHA256: `C012B603571C0F18E4550D39FED3E90E94CD8F20487CED53DBFE222CFAAF9AA2`
- Sidecar and NSIS bundle builds passed. A destructive fresh-install replacement of the user's currently installed profile was not performed; native bridge behavior is covered by Rust/frontend tests and route behavior by Playwright.

## Migration

The version moved consistently from 0.5.0 to 0.6.0 in Backend, Frontend, Tauri, Cargo package metadata, and the installer. Schema setup adds the three notification tables and their indexes/constraints without replacing any prior table. The SQLite migration inserts the disabled-by-default singleton preference with `INSERT OR IGNORE` and records schema `14.0` idempotently.

The 0.5.0 migration fixture preserved existing notice, notice-read, and favorite values across two Gate 14 migration runs. No SQLite reset or destructive rewrite is used.

## Production Protection

- Production server accessed: **NO**
- Production deployment: **NO**
- Production environment/database/Nginx/systemd changed: **NO**
- Real OA login or JLU OA integration attempted: **NO**
- Gate 10D changed: **NO**

## Deferred

- Mobile/Android/iOS notifications
- Web Push and email delivery
- Real OA login/integration
- Production notification deployment and production soak
- Installer auto-update/release pipeline (Gate 15)
- Manual destructive fresh-install replacement and human click-through of an actual Windows Action Center toast

## Git

- Branch: `master`
- Commit: `feat: add notification delivery system` (Gate 14 repository HEAD)
- Working tree after commit: clean
- Pushed: **NO**
