# SQLite to PostgreSQL Migration Plan

## Goals

- Preserve public notice and attachment facts without changing integer notice IDs.
- Copy only public sources (`OFFICIAL_CLOUD` and `SHARED_CLOUD`).
- Exclude client-owned read, favorite, settings and delivery data.
- Allow the command to be repeated safely after interruption.

## Preparation

1. Back up the SQLite file and PostgreSQL database using normal platform tools.
2. Start PostgreSQL and apply the Cloud schema:

   ```powershell
   Set-Location backend
   $env:JLU_DATABASE_URL = "postgresql+psycopg://user:password@host/database"
   .\.venv\Scripts\python.exe scripts/init_cloud_db.py
   ```

3. Stop the old Cloud writer, or otherwise ensure it cannot modify SQLite during the final copy.

## Copy

```powershell
Set-Location backend
.\.venv\Scripts\python.exe scripts/migrate_sqlite_to_postgres.py `
  --sqlite-path .\data\notices.db `
  --database-url "postgresql+psycopg://user:password@host/database"
```

The script first applies the additive Phase 1.5 SQLite columns (`version`, attachment `content_hash`, attachment `created_at`) and then upserts public rows in dependency order:

1. sources;
2. notices;
3. source relations;
4. attachments;
5. notice update history.

SQLAlchemy `merge` uses the preserved primary key, so a rerun updates the same row rather than inserting a duplicate. Existing unique constraints remain a second line of defense. After copying, the migration advances PostgreSQL sequences to each table's maximum imported ID so subsequent Worker inserts cannot collide with preserved IDs.

Even for public sources, the copy clears `auth_username`, credential references, local session-profile references and private-network permission. These values are neither public facts nor required by the official Cloud adapters.

## Verification

Compare the JSON summary printed by the migration with read-only source counts. Then verify:

- `/api/notices?limit=1` reports the expected public total;
- a sample notice ID resolves to the same title, URL and hash;
- the detail response contains the expected attachment count;
- `/api/sources` contains only intended public sources;
- PostgreSQL does not contain client-state tables in the Phase 1.5 schema.

The automated migration tests execute the copy twice and assert stable counts, preserved IDs and the absence of migrated user/favorite rows.

To run the real PostgreSQL integration test against the disposable Compose database:

```powershell
docker compose -f docker-compose.cloud.yml --profile test up -d postgres-test
$env:JLU_TEST_POSTGRES_URL = "postgresql+psycopg://notice_test:notice_test@127.0.0.1:5433/notice_cloud_test"
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests\test_cloud_postgres.py
```

The test requires a database name ending in `_test`; the guard prevents it from dropping a non-test database.

## Cutover and rollback

After verification, start the Cloud API and Worker with PostgreSQL and monitor `/health` plus crawler logs. Desktop continues using SQLite and therefore does not participate in the Cloud database cutover.

Rollback is operational: stop the PostgreSQL Worker/API and restart the former Cloud process against the unchanged SQLite backup. Do not run Alembic downgrade against production as a rollback mechanism; it removes Cloud tables.

## Limitations

- Phase 1.5 is a one-way public-data copy, not continuous bidirectional sync.
- A notice whose primary `source_id` is private is intentionally not copied, even if a secondary relation is public. Such data should be audited and assigned a public primary source before migration.
- Attachment hashes added to legacy SQLite rows are initially null; subsequent crawl observations populate them without downloading attachment bodies.
