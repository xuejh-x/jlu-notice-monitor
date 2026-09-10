# Startup Sync

## Root Cause

`Settings.effective_startup_sync_enabled` previously defaulted to `true` only when
`deployment_role == "desktop"`. The ordinary local backend runs as
`environment=development` and therefore resolves to the `standalone` role. Its
FastAPI lifespan initialized the database and started the scheduler, but skipped
`startup_sync.trigger_once()`. This exactly explains the observed combination of
`crawler=idle`, `scheduler=running`, and `startup_sync.triggered=false`.

The long-lived frontend state had a separate race. After a manual request it set
local `tracking=true`, but cleared it only after observing a response with
`crawler.running=true`. A 2–3 second crawl could complete between polls, leaving
the UI locally stuck even though the backend was idle. Scheduler activity was
also not described independently enough from an active crawl job.

## Fix

Startup sync now defaults on for both `standalone` and `desktop`, while the
`cloud` role remains scheduler-only. `JLU_STARTUP_SYNC_ENABLED` is still an
explicit override; isolated E2E fixtures set it to `false` so tests never crawl
real sites or modify a real SQLite database.

The FastAPI lifespan order is:

1. create runtime directories and configure logging;
2. initialize/migrate SQLite;
3. synchronize source records and importance rules;
4. mark the API ready;
5. enqueue one background startup crawl;
6. start the no-backlog scheduler.

The crawl is never awaited by application startup. Both immediate launch errors
and asynchronous crawl errors are recorded without failing API/Desktop
readiness. Shutdown cancels owned background work through the existing crawler
lifecycle.

`startup_sync` now reports `triggered`, `started_at`, `completed_at`, `outcome`,
and `skipped_reason`. Outcomes include `started`, `success`, `partial_failure`,
`failure`, `skipped_running`, and `cancelled`.

## Scheduler Interaction

Startup, scheduled, per-source, and manual runs still use the one existing
`CrawlerManager` single-flight guard and cross-process lock. No second lock or
queue was added. Startup is enqueued before the scheduler begins its initial
interval. If a scheduled tick or manual action collides with an active crawl, it
uses the existing `CrawlerAlreadyRunning` behavior; the scheduler records
`skipped_running` and creates no backlog. Its next interval remains intact.

Cloud startup sync stays off by default, which also protects the current Gate 10
production deployment from restart-triggered duplicate work.

## Frontend State

“正在检查” now means only that the crawler status has both `running=true` and
`status="running"`. `scheduler.running` means only that the timer loop is alive
and never drives the checking label.

The UI distinguishes active, success, partial-failure, failure, and idle states.
Polling continues while a real crawl or startup synchronization is pending. A
manual crawl can also complete between polls: a changed `last_run` closes the
tracking window without requiring an observed intermediate running state.

On crawl completion the frontend invalidates the authoritative TanStack Query
keys for dashboard, notices, search, source status, and source configuration.
Startup completion is handled once by its `completed_at` identity, so newly
ingested notices appear without a full-page reload.

# OA Integration

## Current State

OA has moved from an adapter that always raised `OA_UNCONFIGURED` to a real,
configuration-driven authenticated adapter foundation. It can parse mocked and
captured authenticated list/detail HTML, emit the shared `NoticeCandidate` and
`AttachmentData` contracts, enter the normal normalization/classification/date/
importance/SQLite pipeline, and report authentication or parser state without
affecting public sources.

OA is **not yet ready for real end-to-end use**. The current development virtual
environment does not contain Playwright, the packaged sidecar currently excludes
Playwright, and no authorized post-login OA DOM has been captured to establish
selectors. The source remains disabled/unconfigured until those conditions are
resolved and validated.

A non-destructive probe from the current machine on 2026-09-10 established only
the following facts: `https://oa.jlu.edu.cn/` was reachable, redirected to
`/defaultroot/login.jsp`, and identified the response as GBK HTML. A direct
`HEAD` request to the login page returned 403. This is not enough evidence to
claim CAS, captcha, MFA, session lifetime, or the authenticated page structure.

## Authentication Model

OA uses an interactive, user-owned browser session. The Sources page calls the
backend reauthentication endpoint; the backend owns a single login coordinator,
opens the dedicated persistent Edge profile, and waits for the user to complete
whatever legitimate SSO, captcha, MFA, or VPN steps the real site requires. The
application never asks for, receives, or automates the user's OA password.

After login, the coordinator validates the configured list selectors and one
detail item before marking the source `authenticated`. An authenticated session
without a verified parser becomes `unconfigured`, not ready. Closing the window,
timing out, or returning to a login page becomes an authentication-required
state. The coordinator is cancelled during FastAPI shutdown.

## Secret Storage

OA cookies/session state live only in the dedicated local browser profile under
the application data directory. They are not placed in SQLite, URLs returned to
the frontend, localStorage, source DTOs, diagnostics, or structured logs. The
profile is excluded from Git and is never uploaded to the Notice Hub cloud.

The existing `CredentialStore` remains the abstraction for other private-source
password/token modes and uses Windows DPAPI. OA deliberately does not save a
password in that store because authentication is browser-driven.

Known credential-like query parameters (`token`, `ticket`, `session`, `sid`,
`authorization`, and equivalents) are removed before OA notice or attachment
URLs may enter persistence or logs. The adapter keeps an in-memory raw URL map
only for the duration of the current crawl so it can fetch a detail page before
persisting the sanitized URL.

## Runtime Placement

OA is a `CUSTOM_LOCAL_PRIVATE` source with `execution=local`. Desktop/standalone
runtimes may execute it; Cloud source resolution excludes all local-private
sources. This is the safe default because Cloud has neither the user's session
nor an established right/network path to OA. Public sources continue to support
their existing Cloud/Desktop execution model.

## Source Adapter

`OASource` stays behind the existing source registry and implements the standard
`fetch_list`, `fetch_detail`, and `close` interface. Authentication/browser
behavior is encapsulated in the adapter and login coordinator; the crawler runner
does not contain OA parsing or login branches.

The list/detail DOM contract requires explicit `item_selector`,
`title_selector`, `link_selector`, and `content_selector`. Attachment and date
selectors are optional. Missing or unverified selectors raise
`SourceNotConfiguredError`, which the runner maps to `unconfigured/skipped`
instead of an ordinary source failure.

## Status Model

- `disabled`: explicitly turned off after configuration.
- `unconfigured`: initial login or authenticated DOM/parser verification is
  incomplete.
- `needs_reauth`: session missing, expired, cancelled, or timed out.
- `authenticated`: browser session and parser smoke check succeeded; ready for a
  crawl.
- `healthy`: the most recent OA crawl completed successfully.
- `network_error`, `auth_error`, `parse_error`, `source_error`: genuine isolated
  runtime failures.

The source-configuration DTO separately exposes `authentication_status` as
`not_required`, `not_configured`, `required`, or `authenticated`. The Sources UI
shows status, authentication state, latest success/error, first-login or
reauthentication action, enablement, and the existing institutional landmark
icon rather than an “OA” letter placeholder.

## Dedup

OA declares `dedup_across_sources=true`. The normal persistence path then uses
the existing high-confidence cross-source URL/title/date matching and creates a
new `NoticeSourceRelation` for OA instead of a duplicate `Notice`. Per-source
content hashes remain independent, and user read/favorite state remains attached
to the canonical notice.

## Attachments

Authenticated detail parsing emits the existing `filename/url/type` attachment
contract, and persistence uses the existing attachment table and duplicate URL
guard. Sensitive query parameters are removed before storage.

Real session-required download behavior is not yet claimed as complete. Once the
authorized OA DOM is available, downloads must be verified using sanitized,
cookie-authenticated URLs. If OA requires a one-time query ticket, a local
authenticated download proxy/opaque reference will be required before enabling
that attachment; the raw ticket must never be stored or exposed.

## Failure Isolation

Login expiry maps only OA to `needs_reauth`. Missing selectors map only OA to
`unconfigured/skipped`. Other OA errors are contained by the existing per-source
runner boundary, so public adapters continue and the aggregate result follows
the existing partial-failure semantics. Tests cover an OA failure alongside a
successful public-source result.

## Security Considerations

- No credential, cookie, token, Authorization header, or sensitive attachment
  query is logged or serialized.
- No login bypass, captcha/MFA automation, or access-control workaround exists.
- OA never runs in Cloud and its profile never enters the public feed.
- Browser/login tests are mocked and contain no real credentials.
- Parser activation requires evidence from a user-authorized session.

## Remaining Manual Setup

1. Connect this machine to a network path where OA is legitimately available
   (campus network or the user's authorized VPN).
2. Install the optional OA runtime in the development environment with
   `python -m pip install -e ".[oa]"`. The current environment reports that
   Playwright is absent.
3. Use Sources → JLU OA → 首次登录 and personally complete the real login. Do
   not send credentials to logs, fixtures, or source code.
4. From that authorized session, capture only the minimum DOM structure needed
   to verify list, title/link/date, detail body, and attachment selectors; add
   the verified selectors to the OA `parser_config`.
5. Validate list → detail → attachment → SQLite on a disposable local database.
   Confirm campus/VPN requirements and session-expiry behavior.
6. Update the Desktop sidecar packaging to include the optional Playwright
   runtime, then build and test a new non-production Desktop artifact.
7. Only after these steps pass may OA be enabled or described as ready. Any
   production rollout requires a separate authorization after Gate 10 re-soak.
