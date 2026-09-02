# Gate 12 — Architecture and Migration Audit

Audit date: 2026-09-02
Starting commit: `db70479d847c7268f0af793bba36d5cfda1e1fd8`
Branch: `master`
Starting working tree: clean
Starting versions: frontend/Tauri `0.3.0`; backend package/runtime `0.2.0`

This document records the repository facts observed before any Gate 12 production-code change. Gate 10D production infrastructure was not accessed or modified.

## Current Architecture

### Desktop lifecycle

- Tauri owns one dynamically-port-bound, loopback-only PyInstaller sidecar.
- `DesktopBackendBoundary` waits for `/api/health`, configures the dynamic API base URL, and only then renders React.
- The FastAPI lifespan initializes SQLite, mirrors `config/sources.yaml` into `sources`, starts the 15-minute scheduler, and reports healthy.
- No startup crawl/synchronization is triggered. The first automatic run waits one full scheduler interval.
- `CrawlerManager` already has an in-process async lock, an on-disk lock, and `CrawlerAlreadyRunning`; scheduler/manual collisions are skipped instead of queued.

### Source model and crawling

- `config/sources.yaml` is the authoritative definition and enable/disable store for five public JLU sites plus disabled JLU OA.
- The `sources` table contains identity, URL, enabled state, timestamps, one free-text error, and an error counter. It has no ownership, subscription, parser, authentication, or explicit health-state columns.
- `SOURCE_TYPES` is a hard-coded registry of five site adapters and OA. Public adapters inherit `StaticHTMLSource`; generic HTML configuration and RSS/Atom are absent.
- A crawl loads YAML on every run, builds enabled adapters, fetches sources concurrently (limit 2), and isolates failure per source and notice.
- OA is the only private-source concept. It uses one global persistent profile path, has a console-driven `input()` login setup, and intentionally refuses to claim a configured logged-in DOM.

### Notices, duplicate handling, and user state

- Factual notice data and the computed importance score share the `notices` table.
- Read/archive/favorite state is already separated into one local `user_states` row per notice. The legacy `favorites` table is kept in sync by the mutation API.
- Source provenance is many-to-many through `notice_source_relations`.
- Duplicate lookup currently prefers canonical URL, then exact normalized title within 14 days, then fuzzy title similarity. Equal title alone can therefore merge across sources; Gate 12 must tighten this for newly introduced ownership domains.
- Attachments and update history are separate tables and must be preserved.

### Importance scoring

- Category classification and keyword scoring are loaded from installation-bundled `config/keywords.yaml`.
- Importance is computed when a notice is inserted or updated and stored locally on `notices.importance_score`.
- The objective components are base score 20, category boosts, and deadline urgency. Four keyword groups contribute fixed group weights plus a repeated-hit bonus.
- There is no user-local rule store, first-run migration, rule API, or historical re-score operation.

### API and frontend

- The local API provides notice queries and state mutations, read-only source status, manual crawler start/status, dashboard, health, and diagnostics.
- There is no versioned public feed, source-management API, preview/test API, auth-state API, or importance-rule API.
- Sources UI is a read-only flat status list. Settings persists display preferences in browser localStorage and has no importance editor.
- Existing React Query invalidation covers notice, dashboard, search, sources, and crawler families.

### Storage and migration

- Production runtime lives under `%LOCALAPPDATA%\JLU Notice Monitor` and already separates SQLite, logs, cache, OA profile, and runtime config directories.
- Schema initialization uses `Base.metadata.create_all()` only. It cannot add columns to an existing Gate 11 database.
- There is no schema-version table or migration runner.
- Gate 12 migration must be additive, transactional where SQLite permits, idempotent, and tested only against copied/temporary databases.

### Baseline verification

- Backend: `62 passed` using the existing repository venv (the sandbox required an outside-sandbox process launch; the venv and tests themselves are healthy).
- Frontend: `27` files / `123` tests passed.
- Frontend lint: passed.
- Frontend production build: passed, 2,794 modules.
- Rust: `4 passed`.

## Gate 12 Target Boundary

### Cloud responsibility

- Crawl only official public source websites.
- Store normalized factual public notices and factual source metadata.
- Serve a versioned, GET-only feed with stable public identities and incremental pagination.
- Never receive or serve desktop read/favorite state, personal rules/scores, custom-source configuration, credentials, cookies, tokens, or browser profiles.

### Desktop responsibility

- Synchronize official facts from the public feed without falling back to direct official crawling when cloud is unavailable.
- Persist cached official facts and local official-source subscription preferences.
- Crawl user-created public and private sources locally.
- Own read/favorite/archive state, personal importance rules and scores, private credentials, sessions, source health, and reauthentication state.

### Deployment roles

- A configured cloud role keeps official adapters enabled and exposes the public feed.
- A desktop role represents built-in official sources as `OFFICIAL_CLOUD` and imports them from the configured feed.
- A compatibility/test role may run the existing adapters locally only when explicitly configured; it is not an outage fallback.
- Gate 12 production deployment remains deferred until Gate 10D final acceptance.

## Data Model and Migration Plan

1. Add an idempotent `schema_migrations` table and an ordered migration runner before ORM `create_all` completes startup.
2. Extend `sources` additively with ownership, source kind/parser, subscription, explicit health/auth state, parser configuration, auth metadata, last error code, and reauth-prompt suppression metadata.
3. Backfill the five public built-ins as `OFFICIAL_CLOUD`, OA as `CUSTOM_LOCAL_PRIVATE`, and preserve every existing source id and relation.
4. Add `importance_rules` with local enabled/keyword/weight/system-default metadata and initialize it once from bundled defaults.
5. Add a small local settings/sync-state store for feed cursors and migration flags.
6. Add a stable optional public notice identity while preserving existing notice ids, relations, user state, attachments, and updates.
7. Keep secrets outside SQLite source configuration. Store only a credential reference; use Windows DPAPI-backed local secret files and a test-only volatile implementation on unsupported test hosts.
8. Move authenticated browser state to one profile directory per source and retain the existing OA profile through a non-destructive compatibility path.

## Reliability and Security Plan

- Add one backend-owned startup trigger per process; use the existing crawler lock so startup, scheduler, and manual runs cannot overlap.
- Split a run into official-feed synchronization plus enabled local-source jobs while keeping per-source failure isolation.
- Reject non-HTTP(S), credential-bearing, loopback, link-local, multicast, and private-network URLs for custom public sources; revalidate redirects and cap redirects, response bytes, items, pagination, retries, and timeouts.
- Permit private-network targets only for an explicitly private source with an explicit local-network opt-in.
- Sanitize parser output to text/validated URLs; never render fetched HTML in React.
- Never return secret values from source APIs or write them to logs.
- Pause private sources in `NEEDS_REAUTH` and suppress repeated interactive attempts until the user explicitly starts reauthentication.

## Planned Internal Stages

1. Add migrations and the expanded local domain model.
2. Add startup orchestration and Cloud-first feed import/export.
3. Add subscriptions and custom public HTML/RSS preview/CRUD.
4. Add generic private-source auth/session states and DPAPI credential references.
5. Add personal importance rules and deterministic whole-database re-score.
6. Extend existing Sources and Settings surfaces without changing the approved desktop shell.
7. Complete security, migration, API/frontend/Rust/E2E regression, version `0.4.0`, and isolated installer QA.

This audit is the factual pre-change checkpoint for Gate 12. It does not claim any Gate 12 acceptance item is implemented yet.
