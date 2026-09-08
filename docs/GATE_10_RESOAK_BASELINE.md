# Gate 10 Re-Soak Baseline

## Status

**SOAK RUNNING**

Gate 10 remains **FAIL — re-soak running**. This record starts a new production observation window for the fixed Gate 10 artifact; it does not grant final acceptance.

## Reason

The previous production artifact completed 167.858 hours of soak and met the availability, SQLite, backup, TLS, and resource thresholds. It cannot be credited to this artifact because the soaked version had a confirmed incremental-fetch blocker: in a representative 81-notice unchanged round it fetched 41 detail pages, including 30/30 for `csw`.

The crawler fix changes production behavior, so the fixed artifact requires its own continuous production evidence for at least 72 hours.

## Fixed Blocker

- Original issue: list parsers may omit optional `publish_date` or `publisher` fields while detail parsers enrich and persist them. The old cheap-change detector compared the missing list values strictly with the enriched database values and fetched the same detail pages every round.
- Root cause: `CrawlerManager._find_unchanged_list_item` treated absent optional list metadata as a change.
- Fix: the title remains a strict comparison; a list date or publisher is compared when the list actually supplies it; an absent optional list value no longer invalidates richer stored detail metadata.
- Regression coverage: `test_incremental_skip_when_detail_enriches_optional_list_metadata` proves that the first run fetches/enriches the detail and the next unchanged run skips it. Existing orchestration and database tests continue to cover new, updated, unchanged, `last_seen_at`, source isolation, and scheduler semantics.
- Scope: no API contract, URL schema, database schema, scheduler behavior, persistence model, frontend behavior, or crawler adapter was changed.

## Production Version

- Git commit SHA: `538bb7c056e3e3b7a6339a2c4de296bbbb87140d`
- Branch: `codex/gate10-resoak`
- Base production commit: `d9042b0f3b21d05a7284b48df16133e7a8c9b469`
- Local review commit: `3330e46fd7fca0bba759ce466a61e9cf580d1123`
- Deployment start: `2026-09-08 19:03:03 CST` (`Asia/Shanghai`)
- Service restart: `2026-09-08 19:05:19 CST`
- Deployment complete: `2026-09-08 19:05:21 CST`
- Verification method: the production repository reports the exact branch and SHA above, its working tree is clean, its Git tree is `92637990860a6c5184c82b860c859ba22aab8541`, and the deployed `runner.py` blob is `a68066549045123fc9b10017599bf739db16fcc6`. The systemd service was restarted only after these checks and now runs from `/opt/notice-hub/app/backend`.
- Deployment scope from `d9042b0`: `backend/app/crawler/runner.py`, its direct regression test, and the Gate 10 acceptance report only. Later Gate 12–14 product code was not deployed.

## Soak Window

- Start: `2026-09-08 19:13:15.359578 CST` (`Asia/Shanghai`, `2026-09-08T11:13:15.359578Z`)
- Required minimum duration: `72h`
- Earliest eligible acceptance time: `2026-09-11 19:13:15.359578 CST` (`Asia/Shanghai`)
- Start evidence: first structured soak record containing the fixed production Git SHA and the incremental per-source metrics; `overall=ok`.
- Historical rule: records before this start remain preserved but are excluded from the fixed-artifact acceptance window.

## Deployment Verification

- Backend: `notice-hub.service` is active and enabled; PID `48611`; service activation `2026-09-08 19:05:19 CST`; `NRestarts=0` after deployment.
- Nginx: active and enabled; existing activation retained; `NRestarts=0`.
- Health: loopback `/api/health` returns HTTP 200 with `status=ok`, `database=ok`, `crawler=idle`, `scheduler=running`, `environment=production`.
- Public boundary: HTTP returns `301` to HTTPS; unauthenticated HTTPS API returns `401`; FastAPI remains loopback-only on `127.0.0.1:8000`.
- Diagnostics: initialized, database healthy, crawler success, scheduler enabled/running, no latest source error.
- Database: `/var/lib/notice-hub/data/notices.db`, `quick_check=ok`, existing historical data retained, no schema migration or rebuild.
- Scheduler: enabled and running at 15-minute intervals. The first post-deployment scheduled run started at `2026-09-08 19:20:21 CST`, completed successfully at `19:20:23 CST`, and set the next run to `19:35:23 CST`. No duplicate crawler process or backlog was present.
- Operations: `notice-hub-soak.timer`, `notice-hub-backup.timer`, and `snap.certbot.renew.timer` are active and enabled.

## Incremental Verification

The fixed artifact completed a safe real production crawler cycle from `2026-09-08 19:06:01` to `19:06:04 CST`.

- Result: `success`
- Trigger: `manual`
- Duration: `1.746s`
- Total list notices: `81`
- New: `0`
- Updated: `0`
- Unchanged: `81`
- Detail fetched: `2`
- Detail skipped: `79`

| Source | List | Detail fetched | Detail skipped | New / updated / unchanged | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `cse` | 11 | 1 | 10 | 0 / 0 / 11 | success |
| `ccst` | 10 | 0 | 10 | 0 / 0 / 10 | success |
| `csw` | 30 | 0 | 30 | 0 / 0 / 30 | success |
| `jwc` | 15 | 1 | 14 | 0 / 0 / 15 | success |
| `innovation` | 15 | 0 | 15 | 0 / 0 / 15 | success |
| `oa` | 0 | 0 | 0 | 0 / 0 / 0 | skipped/disabled |

`csw` changed from the blocker signature of 30 fetched / 0 skipped to 0 fetched / 30 skipped. A read-only list-versus-database comparison classified the two remaining detail fetches:

- `cse`: one list item had a real title change relative to the stored title.
- `jwc`: one list item had a real title change and a supplied publish date (`2025-08-25`) different from the stored detail date (`2025-09-02`).

Both are deliberate cheap-change-detector triggers. Neither is caused by absent optional list metadata, and both persisted as `UNCHANGED` after detail/content comparison.

### First scheduled-cycle confirmation

The first normal scheduler-triggered cycle on the fixed process independently reproduced the manual verification:

- Scheduler start: `2026-09-08 19:20:21 CST`
- Crawler completion: `2026-09-08 19:20:23 CST`
- Result/outcome: `success` / `success`
- Duration: `1.879s`
- Total list / new / updated / unchanged: `81 / 0 / 0 / 81`
- Detail fetched / skipped: `2 / 79`
- `csw`: `30` list, `0` detail fetched, `30` detail skipped
- Scheduler next run: `2026-09-08 19:35:23 CST`
- Scheduler last error: `null`
- Overlap, skipped-running, source failure, and detail failure events since deployment: `0`

The enhanced checker immediately persisted this scheduled round, so later acceptance does not depend on an in-memory diagnostics snapshot.

## Baseline Metrics

Captured between `2026-09-08 19:09:39` and `19:13:15 CST`.

- Notices: `88`
- Sources: `6` (`cse`, `ccst`, `csw`, `jwc`, and `innovation` healthy; `oa` disabled as configured)
- Notice/source relations: `93`
- Attachments: `68`
- User states: `88`
- Notice updates: `0`
- Favorites legacy table rows: `0`
- Database size: `454,656 bytes`
- Database quick check: `ok`
- Duplicate canonical URLs: `0`
- Duplicate per-source URLs: `0`
- Maximum notice/relation `last_seen_at`: `2026-09-08 19:06:03.440355 CST`
- Log directory after scheduled-cycle capture: `2,580,404 bytes` (approximately `2.5 MiB`)
- Active app log: `871,631 bytes`
- Active soak log: `175,336 bytes`, `80` current-file records
- Root disk: `40 GiB` total, `5.8 GiB` used, `32 GiB` available, `16%` used
- Inodes: `5%` used
- Memory: approximately `1.6 GiB` total and `1.1 GiB` available at baseline
- Swap: `2.0 GiB` active, `0` used
- Latest backup: `/var/backups/notice-hub/notices-20260908T031928.db`, `454,656 bytes`, `quick_check=ok`
- Errors since deployment: `0` journal warning-or-higher entries, `0` application error/critical events, and no immediate Gate blocker

## Soak Observability

The existing checker was insufficient for this re-soak because it did not persist detail-fetch totals or per-source detail statistics. It was minimally and backward-compatibly enhanced before the formal start:

- Every new sample records the production Git SHA/branch.
- Every new sample records list fetched, detail fetched, detail skipped, NEW, UPDATED, UNCHANGED, and per-source values.
- `notice-hub-soak-report` accepts `--since <ISO-8601>` so the old 167.858-hour evidence is retained but excluded from this artifact's report.
- Server backups: `/usr/local/sbin/notice-hub-soak-check.bak.20260908T191315` and `/usr/local/sbin/notice-hub-soak-report.bak.20260908T191315`.
- The first enhanced checker execution completed successfully with `overall=ok`; no crawler, scheduler, database, log history, backup, Nginx, or TLS configuration was changed.
- The regular `notice-hub-soak.timer` invoked the enhanced checker at `19:15:28 CST` and exited successfully; the scheduled crawler result was also captured at `19:20:26 CST`.
- Initial filtered report self-check: `3/3` successful checks, `0` failures, `0` warnings, one unique scheduled crawler success, only production SHA `538bb7c...`, detail fetched/skipped `2/79`, and `csw` fetched/skipped `0/30`.

## Regression

- Backend on the current development line: `114/114 PASS`
- Incremental crawler orchestration: `5/5 PASS`
- Frontend unit/integration: `28 files, 143/143 PASS`
- Frontend lint: `PASS`
- Frontend production build: `PASS` (`2802` modules transformed)
- Browser E2E: `18/18 PASS`
- Exact production release branch backend suite: `63/63 PASS`

## Known Issues

None blocking soak.

Non-blocking build note: Vite reports one approximately `510.92 kB` pre-compression JavaScript chunk. This did not fail tests, lint, build, E2E, or production verification.

## Acceptance Requirement

**Gate 10 remains FAIL until the fixed production artifact completes >=72h soak and passes final acceptance.**

At or after the earliest eligible time, run the version-filtered production report and then repeat the full process in `docs/GATE_10_FINAL_ACCEPTANCE.md`:

```bash
/usr/local/sbin/notice-hub-soak-report --since '2026-09-08T19:13:15.359578+08:00'
```

Final acceptance must additionally confirm that the report covers at least 72 real hours, contains only production Git SHA `538bb7c056e3e3b7a6339a2c4de296bbbb87140d`, has no blocking availability/database/scheduler/source/TLS/backup/resource incidents, and shows that incremental skipping remains healthy—especially for `csw`. Run the repository regression commands documented in `docs/GATE_10_FINAL_ACCEPTANCE.md` again before changing Gate 10 from FAIL to PASS.
