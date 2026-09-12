# Stage 17.2 — Cloud Preferred Local Fallback

## Result

PASS. Desktop can execute an Official Public Source with `execution_policy=cloud_preferred` as one SourceRun containing a Cloud attempt followed, only when eligible, by a Local Adapter attempt. Shared Cloud and Private/Custom Local sources retain their previous execution behavior.

## Architecture Changes

- The existing scheduler remains the only scheduler. It still schedules one run per source.
- A source run now exposes ordered `attempts`. A successful Cloud attempt ends the run, including a successful empty response. An eligible Cloud failure starts the Local attempt serially in the same run.
- Fallback eligibility is restricted to Desktop, `ownership=OFFICIAL_CLOUD`, `execution_policy=cloud_preferred`, `parser=cloud_feed`, and a known built-in Local Adapter.
- The final source result exposes `execution_policy`, `effective_execution`, `fallback_used`, and `fallback_reason`. A recovered Local attempt produces one successful final result; an unsuccessful Local attempt produces one failed final result.
- No persistent fallback state was introduced. Every later scheduled/manual run starts with Cloud again.

## Fallback Flow

1. The existing scheduler starts one Official Public SourceRun.
2. Desktop executes the Cloud Feed adapter.
3. A valid response, including an empty item list, completes the SourceRun with `effective_execution=cloud`.
4. Feed-not-configured, network, timeout, HTTP, invalid-response, or expired-data errors start the built-in Local Adapter.
5. Local success completes the same SourceRun with `effective_execution=local` and `fallback_used=true`.
6. Local failure completes the same SourceRun as failed while preserving both attempt records.

Cloud freshness is an additive v1 feed field, `source_last_success_at`. Desktop treats a present-but-null or older-than-threshold timestamp as expired. The default threshold is 3,600 seconds. Older v1 servers that omit this new field remain compatible and skip only the freshness check.

## Notice Identity and Deduplication

- `origin_item_key` is stored on `NoticeSourceRelation`, where source-scoped identity belongs.
- Identity priority is source-native ID first, otherwise SHA-256 of the canonical URL.
- Public Cloud Feed responses expose the origin key; the Local Adapter derives the same key from its native ID or URL.
- Stage 17.2 migration backfills existing relations with canonical URL hashes without rebuilding notice tables.
- The existing deduplication service is unchanged. The runner resolves a source relation by `origin_item_key` before invoking the existing duplicate finder.
- `NotificationEvent` and `NotificationDelivery` are unchanged. Cloud/Local observations resolve to one Notice ID, so their existing event dedupe keys continue to prevent duplicate notifications.

## API and Frontend

- Public Feed notice payload adds `origin_item_key` and `source_last_success_at`; existing fields and version remain unchanged.
- Crawler status SourceResult adds ordered `attempts`, `fallback_used`, and `fallback_reason` while retaining `execution_policy` and `effective_execution`.
- Sources shows read-only execution badges: `云端运行` or `本地回退生效`. There is no execution-policy editor.

## Tests

- Backend: 142 passed. Coverage includes Cloud success/no fallback, Cloud failure/Local success, both attempts failing, Shared Cloud exclusion, Cloud/Local identity dedupe, one NotificationEvent, stale Cloud metadata, and idempotent migration.
- Frontend: 28 files, 176 tests passed.
- Frontend lint: PASS.
- Frontend production build: PASS (2,804 modules). The existing bundle-size warning remains non-blocking.
- E2E: 25 passed, including Sources fallback status.

## Limitations

- No circuit breaker, half-open probe, sticky fallback state, or separate recovery workflow.
- No fallback for Shared Cloud, custom public, or private sources.
- Fallback requires a built-in Local Adapter present in the Desktop bundle/YAML configuration.
- Older v1 Cloud Feed deployments that omit `source_last_success_at` cannot provide stale-data detection, although network/timeout/HTTP fallback still works.
- Freshness relies on Cloud/Desktop UTC clocks and a fixed configurable threshold.
- Multiple Desktop devices may independently fall back and contact the official origin; multi-device coordination is intentionally not implemented.

## Release Readiness

Repository implementation and automated regression gates are ready. A release installer was not built in this stage. For deployment, update the Cloud Feed first so it emits the additive identity/freshness fields, then release Desktop; the Desktop remains compatible with an older v1 feed during rollout.
