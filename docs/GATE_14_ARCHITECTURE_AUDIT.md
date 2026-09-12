# Gate 14 Architecture Audit — Notification Delivery & User Reminder System

Date: 2026-09-03

Baseline: `0.5.0` / `ece8527f01008a1a51c8568de7629370e1a95658`

Scope: local Desktop only; production, OA login, mobile, web push and Gate 15 are excluded.

## Executive decision

Gate 14 needs a separate local notification subsystem. A notice is shared content; a notification event is a reason to alert this device; a delivery record is the durable hand-off state for one channel. Notice rows and `user_states` must not be overloaded.

The accepted shape is:

```text
Notice / Source / local-day aggregate
                |
                v
       NotificationEvent  -- durable semantic dedupe key
                |
                v
      NotificationDelivery -- PENDING -> SENDING -> DELIVERED / FAILED / UNCERTAIN
                |
                v
      Desktop claim API -> Tauri notification plugin -> Windows notification
```

All personal Gate 14 rows live in the Desktop SQLite database and are never part of the public cloud feed. The notification API and event generation are disabled for the cloud deployment role.

## Backend audit

### Notice creation and update detection

`CrawlerManager._persist_candidate` normalizes the title and URL, computes a content hash, extracts dates and importance, then calls `find_duplicate`. A missing duplicate creates a `Notice`, `UserState`, and `NoticeSourceRelation`; non-bootstrap inserts return `NEW`. An existing source relation whose content hash changed creates `NoticeUpdate`, updates the canonical notice fields, and returns `UPDATED`. An unchanged list item is short-circuited by matching source URL plus title, publish date, and publisher. Crawler retries therefore already converge at the notice layer, but there is no reminder event produced from those states.

Deadline changes are currently implicit in a changed notice: the old deadline is overwritten and only the old/new content hashes survive in `NoticeUpdate`. Gate 14 must capture the old deadline before mutation and create a `DEADLINE_CHANGED` event in the same database transaction.

### Existing data that can be reused

- `Notice.importance_score` is the objective score used for an important-notice threshold.
- `Notice.registration_deadline` is the reminder date source.
- `Notice.first_seen_at`, `publish_date`, and `status` distinguish live inserts from bootstrap history.
- `Source.health_state`, `last_error_code`, `consecutive_errors`, and the previous state at the start of a run support transition-based health events.
- `UserState.is_read`, `is_favorite`, and `is_archived` are local personal notice state.
- `CrawlerManager` and `CrawlerScheduler` expose committed new/update results and a no-backlog periodic lifecycle.

### Existing event model

There is no general event model. `NoticeUpdate` is an audit row for changed content, not a user-facing reminder: it cannot represent new notices, deadline lead times, source health or daily summaries, and has no delivery lifecycle. `AppState` is key/value process state and is also not an event store.

### Read-state boundary

`UserState.is_read` must remain “the user opened/read the notice”. Notification read state means “the user viewed this reminder in the Bell popover” and belongs on `NotificationEvent.read_at`. Opening a reminder may navigate to a detail route, whose existing auto-read behavior can independently mark the notice read.

### Scheduler reuse

The existing crawler scheduler provides the correct app lifecycle and no-backlog pattern, but its 15-minute crawl interval and crawler-enabled setting cannot be the only clock for reminders. Gate 14 should add a lightweight local notification scheduler with the same start/shutdown pattern. It will periodically generate deadline and daily-summary events; crawler commits will generate new/update/source-transition events immediately. Unique database keys make concurrent passes safe.

## Frontend audit

The Dashboard, list, and detail already expose the counts and `/notices/:id` route needed by notification bodies and click navigation. Detail auto-read is keyed by notice id and must remain unchanged.

Settings currently has a localStorage-backed display settings object plus database-backed importance rules. The visible “通知偏好” section currently controls the Dashboard priority collection, not operating-system notifications. Gate 14 must add a small, separately named “桌面提醒” section rather than reinterpret those controls.

The header Bell already owns an accessible popover, but it displays crawler summary values only. It can be upgraded in place to list recent `NotificationEvent` rows, show a notification unread badge, mark reminders read, and navigate only when an event has a validated internal route. This is deliberately not a full message center and does not change the three-column or mobile navigation structure.

Notification preferences cannot remain only in localStorage because the backend generates and filters durable events even when no settings page is mounted. They belong in a singleton SQLite `notification_preferences` row. This remains device-local personal data. Frontend query caching may mirror it, but the database is authoritative.

## Tauri audit

The shell currently manages a FastAPI sidecar, single-instance focus, shell/opener plugins, startup, and graceful sidecar shutdown. It has no notification dependency, permission capability, send command, or click-to-router event bridge.

Gate 14 will add Tauri's notification plugin and the minimum `notification:default` capability. The web layer will claim a durable delivery from the local backend, ask Tauri to display a concise Windows notification, and acknowledge the result. The notification carries only an allow-listed internal path (`/notices/<positive integer>` or an approved app page). A native activation is forwarded to React Router; invalid or missing paths fall back to the notification list/popover and never to an external URL or malformed detail page.

## Durable model and state machine

### `notification_preferences`

A singleton device-local row stores: master enabled, new notice, important notice, deadline, source health, daily summary, minimum importance, lead-day set, quiet start/end, daily summary time, and timestamps. Defaults are conservative and valid without any migration prompt.

### `notification_events`

Stores type, durable `dedupe_key`, optional notice/source foreign keys, severity, concise title/body, optional validated internal route, local date/bucket, read timestamp, creation timestamp, and next eligible time. `dedupe_key` is unique.

### `notification_deliveries`

Stores event id, channel (`WINDOWS_NATIVE`), status, attempt count, claim token, timestamps, and a bounded/sanitized error. `(event_id, channel)` is unique.

State transitions:

```text
PENDING --durable claim--> SENDING --native API accepted--> DELIVERED
                              |--definite failure-------> FAILED --retry claim--> SENDING
                              |--process/ack ambiguity--> UNCERTAIN (no automatic retry)
```

An expired `SENDING` claim is converted to `UNCERTAIN`, not silently resent. This prevents duplicate Windows notifications after an app/backend crash in the irreducible gap between OS acceptance and the delivered acknowledgement.

## Dedupe rules

- `NEW_NOTICE:<notice_id>`
- `IMPORTANT_NOTICE:<notice_id>`
- `DEADLINE_APPROACHING:<notice_id>:<deadline ISO date>:<lead days>`
- `DEADLINE_CHANGED:<notice_id>:<old-or-none>:<new-or-none>`
- `SOURCE_AUTH_REQUIRED:<source_id>:<health transition fingerprint>`
- `SOURCE_ERROR:<source_id>:<health transition fingerprint>`
- `DAILY_SUMMARY:<user local ISO date>`

The unique event key is the semantic exactly-once boundary. Repeated crawls, restarts, and scheduler passes use insert-or-ignore behavior. A changed deadline creates a new deadline identity; each configured lead-day bucket is independently unique. Deleting the local database intentionally removes this history and permits regeneration.

When both generic-new and important alerts are enabled, an important notice produces `IMPORTANT_NOTICE` as the user-visible alert instead of a second generic toast. This arbitration avoids double-alerting while preserving distinct event types.

## Exactly-once guarantee scope

Gate 14 can guarantee database-level uniqueness of events and at most one successful claim completion per event/channel. It can also prevent automatic resend after an ambiguous crash by persisting `SENDING` before calling Windows and quarantining stale claims as `UNCERTAIN`.

It cannot prove end-to-end exactly-once display because SQLite and the Windows notification platform do not share a transaction: the OS may accept a notification immediately before the process dies without recording `DELIVERED`. Retrying that ambiguous attempt risks a duplicate, so Gate 14 chooses no automatic retry for ambiguity. Definite pre-acceptance failures are persisted as `FAILED` and may be retried. The accurate description is **persistent semantic dedupe with at-most-once native enqueue and best-effort delivery**, not mathematical exactly-once across the OS boundary.

## Quiet hours and local time

Daily-summary identity and quiet-hour evaluation use the Desktop user's local wall-clock date/time, not UTC server assumptions. During quiet hours an event remains pending with `available_at` set to the next quiet-hours end; it is not discarded or repeatedly recreated. A disabled category creates no new user-visible event; turning the master switch off prevents claims and daily-summary backlog growth.

## Source health severity

Health reminders are transition-based to avoid repeated alerts on every crawl:

- `cloud_unconfigured` / `PUBLIC_FEED_NOT_CONFIGURED`: `info`, not a serious failure.
- `needs_reauth`, `AUTH_EXPIRED`, `AUTH_ERROR`: `warning` and `SOURCE_AUTH_REQUIRED`.
- network, parse, and other genuine source failures: `error` and `SOURCE_ERROR`.
- recovery to healthy does not create a required Gate 14 toast.

## Backward-compatible migration

`Base.metadata.create_all` creates the three new tables, indexes, and constraints for existing and fresh databases without replacing old tables. The Gate 14 SQLite migration inserts the one default preference row with `INSERT OR IGNORE` and records schema version `14.0`; both operations are idempotent. Existing notices, attachments, user states, favorites, sources, subscriptions, mappings, credentials metadata, importance rules, and app state are untouched. The migration test constructs representative 0.5.0 data, runs the additive schema creation and Gate 14 migration twice, then verifies both preserved rows and usable new tables.

## Audit answers

1. **How are new/updated notices identified?** `find_duplicate` plus a per-source relation and content hash; `_persist_candidate` returns `NEW`, `UPDATED`, or `UNCHANGED`, with bootstrap inserts intentionally treated as unchanged.
2. **Is there an event model?** No. `NoticeUpdate` is content-change history only.
3. **Can read state be reused?** No. Notice read and notification read have different meanings and storage.
4. **Where should delivery state live?** In Desktop SQLite `notification_deliveries`, linked to durable local `notification_events`.
5. **Does Desktop notification support already exist?** No. The Tauri lifecycle exists, but the notification plugin, permission, delivery bridge, and activation routing do not.
6. **Can the scheduler be reused?** Its lifecycle/no-backlog design can; a separate short local reminder scheduler is required alongside crawler scheduling.
7. **How are duplicate alerts avoided?** Unique semantic event keys, unique event/channel deliveries, durable claim tokens, a single-instance Desktop shell, persisted pre-send `SENDING`, no retry of stale ambiguous claims, and category arbitration.
8. **Which table owns preferences?** A device-local singleton `notification_preferences` table, not cloud data and not `user_states`.
9. **How is migration backward compatible?** Add-only tables/indexes/default row plus an idempotent schema marker; no table reset, replacement, or old-row rewrite.
