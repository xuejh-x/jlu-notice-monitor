# Gate 13 Architecture Audit

Date: 2026-09-02  
Baseline: `af9ec71c22247b0f595dae08bdf1423e50f17486` (`master`, version 0.4.0)  
Scope: Gate 12.5 manual Cloud promotion plus generic private connector completion. Production and real JLU OA are excluded.

## Audited surfaces

- Backend: `Source`, notice/source relations, additive migrations, source management DTOs, crawler manager, scheduler, Cloud feed, generic HTML/RSS/authenticated HTTP adapters, DPAPI credentials, health states, URL safety, deduplication, attachments, and startup sync.
- Frontend: Sources groups and rows, preview/editor flow, source API client and types, Settings-owned local preferences, Radix dialogs, and Desktop/mobile layout.
- Tauri: Rust-owned sidecar lifecycle, loopback dynamic port, app-data paths, cleanup, packaging, CSP, and command boundary. Gate 13 needs no new Tauri command.
- Cloud: the same backend binary in `cloud` deployment role, public incremental GET feed, official-source registry, crawler scheduling, and SQLite source records.
- Tests/docs: Gate 11/12 reports, Gate 12 migration/fixture coverage, Vitest, Playwright, Rust, packaging scripts, and design specification.

## Audit answers

1. **How did a local custom source and Cloud source identify sameness before Gate 13?** They did not have source-level identity. Only notices had `canonical_url`, optional Cloud `public_id`, title/date similarity, and source relations. A local and Cloud source could therefore remain two crawler records even when their notice rows deduped.
2. **Was canonical URL or stable source identity already present?** Notice canonicalization existed. A stable source identity did not. Gate 13 adds `source_identity = SHA-256(canonical source URL)` and `cloud_source_id`. Canonicalization lowercases scheme/IDNA host, removes default ports/fragments/trailing slash and tracking parameters, and sorts remaining query parameters. Meaningful query parameters remain identity-bearing. RSS and page URLs are not guessed to be aliases; a future verified alias registry can map them explicitly.
3. **How is duplicate local/Cloud crawling prevented after promotion?** Promotion mutates the existing local `Source` row in place to `ownership=SHARED_CLOUD`, `source_scope=shared`, `execution=cloud` and stores `cloud_source_id`. Desktop config resolution then selects `CloudFeedSource`, never the old local HTML/RSS adapter. Notice/source foreign keys and user state remain attached to the same local source/notice IDs.
4. **Is a Cloud source shared by all users who enable it?** Yes. Cloud crawls one `SHARED_CLOUD` registry row and publishes facts through the existing incremental feed. Desktops reconcile the public source registry. A newly discovered shared source defaults to locally unsubscribed rather than appearing automatically.
5. **Do subscriptions remain independent and local?** Yes. `subscribed` remains in each Desktop SQLite database. It is not part of the public notice payload or Cloud administration request.
6. **Do favorites/read state remain local?** Yes. `user_states`, `favorites`, and importance rules never enter the Cloud feed or admin API. In-place promotion avoids ID replacement.
7. **Is there a user account or RBAC system?** No.
8. **Can this Gate avoid users/roles?** Yes. A single server-configured administrator key is sufficient for Cloud source mutations. Feed reads remain unauthenticated and rate limited separately.
9. **How can the Cloud scheduler accept manual override?** `cloud_policy` is resolved before a Cloud run: `force_enabled` wins over disabled state, `force_disabled` always prevents execution, and `auto` follows enabled state. Optional `crawl_interval_seconds` is honored for scheduled runs with a 15-minute minimum; manual runs remain explicit.
10. **Does automatic promotion exist?** No mature promotion algorithm exists. Gate 13 does not invent one. `auto` plus `resolve_cloud_execution()` is the clean policy interface for a future algorithm; it cannot override either forced state.
11. **What generic private-source gaps existed?** Gate 12 already had ownership, DPAPI references, per-source profile paths, warning/re-login UI, pause-on-reauth, authenticated HTTP headers, attachment extraction, and secret redaction. The generic HTTP adapter lacked deterministic expiry detection for 401/403 and login redirects and lacked a connected-peer check after DNS validation. Gate 13 fills those gaps and verifies authenticated attachment metadata with fixtures. A packaged arbitrary interactive-browser profile workflow is not required by the currently supported HTTP connectors and remains deferred; no unverified OA/browser automation was added.
12. **Which schema changes are additive?** `source_identity`, `cloud_source_id`, `source_scope`, `execution`, `cloud_policy`, `crawl_interval_seconds`, `validation_status`, and `validated_at`. Gate 13 uses `ALTER TABLE ADD COLUMN`, indexes, deterministic backfill, and a `13.0` migration marker; it drops or rebuilds no table.

## Resulting source model

| Product meaning | ownership | scope | execution | subscription |
| --- | --- | --- | --- | --- |
| Official Cloud source | `OFFICIAL_CLOUD` | `official` | `cloud` | local per Desktop |
| Admin-promoted shared source | `SHARED_CLOUD` | `shared` | `cloud` | local per Desktop |
| Personal public source | `CUSTOM_LOCAL_PUBLIC` | `personal` | `local` | local |
| Private/authenticated source | `CUSTOM_LOCAL_PRIVATE` | `private` | `local` | local |

The existing fields remain authoritative where they already expressed Gate 12 behavior. New fields provide the missing identity/policy boundary rather than replacing notice, subscription, health, or credential models.

## Promotion transaction boundary

1. Desktop requires the stored `validation_status=passed` result from Test/Preview.
2. The user enters an administrator key in a password input; the frontend sends it once to the loopback sidecar.
3. The sidecar forwards it only in `X-Notice-Hub-Admin-Key` to the configured HTTPS Cloud URL.
4. Cloud performs constant-time auth, request validation, DNS/IP/redirect/peer safety validation, fetch, parse, and preview.
5. Cloud creates or reuses the source by stable identity and returns its stable ID.
6. Desktop updates the existing local source row in place and preserves local subscription plus notice/user-state rows.
7. Subsequent Desktop crawls use the source-scoped incremental Cloud feed cursor.

## Security boundary

- `NOTICE_HUB_ADMIN_KEY` is Cloud configuration only; it has no default, is absent from bundles, SQLite and localStorage, and is cleared from UI state after success or failure.
- Missing key returns 401, invalid key 403, unconfigured service 503. Failed authentication has a lightweight per-IP process-local rate limit. Admin bodies are capped at 64 KiB and DTOs reject extra fields.
- Only HTTP(S) source URLs without embedded credentials are accepted. Loopback, private, link-local, multicast, reserved, unspecified, IPv4/IPv6 and metadata addresses are denied. Every redirect is revalidated; when the transport exposes the connected peer, it is checked before response bytes are consumed.
- Public sources cannot carry auth configuration. Private credentials and browser state remain device-local under app data. Logging redacts key/password/token/cookie/authorization/credential/secret fields.
- Production HTTPS termination remains deployment configuration; no production host was contacted during this Gate.

## Tauri and packaged Desktop

The existing Rust shell owns sidecar start/health/termination and publishes only the dynamic loopback API URL. Promotion is an application-backend operation, so no new privileged Tauri command or filesystem grant is needed. Existing private app-data directories continue to own SQLite, DPAPI files, logs, cache and any per-source profile paths.

## Explicit exclusions

- No JLU OA endpoint, selector, credential, cookie, CAPTCHA, SSO, attachment, session or campus-network behavior was implemented or tested.
- No user table, registration, login account, JWT, role, moderator, dashboard, marketplace, ML promotion or updater was introduced.
- Production deployment remains deferred until Gate 10D acceptance.
