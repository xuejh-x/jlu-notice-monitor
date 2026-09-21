# Phase 1.5 Cloud Data Layer Architecture

## Scope

Phase 1.5 introduces a PostgreSQL-backed public data plane without replacing the Desktop runtime. It deliberately does not add accounts, per-user synchronization, push delivery, Flutter, or multi-school administration.

```text
Existing Source Adapters
          |
     Cloud Worker
          |
      PostgreSQL
          |
  Public Cloud API
          |
 Desktop / future clients
```

## Runtime boundaries

| Runtime | Entry point | Database | Responsibility |
| --- | --- | --- | --- |
| Desktop | `app.main:app` | SQLite | Cached public facts plus read, favorite, settings and local NotificationEvent state |
| Cloud API | `app.cloud.main:app` | PostgreSQL | Read-only public notice, source and attachment API |
| Cloud Worker | `python -m app.cloud.worker` | PostgreSQL | Existing adapter scheduling, parsing, deduplication and fact updates |
| Migration job | `scripts/init_cloud_db.py` | PostgreSQL | Alembic schema upgrade before API/Worker startup |

`JLU_DEPLOYMENT_ROLE=cloud` is the hard boundary. In that role the crawler still performs NEW / UPDATED / UNCHANGED detection, relation maintenance, attachment collection and importance scoring, but it does not create `UserState`, `Favorite`, `NotificationEvent` or `NotificationDelivery` records. Desktop behavior remains unchanged.

## Compatibility guarantees

- Existing Source Adapter implementations and source YAML remain the crawler source of truth.
- Desktop SQLite initialization remains additive and retains existing data.
- The existing Desktop `/api/notices` contract remains unchanged. The Cloud API is a separate FastAPI application even though its route names are intentionally simple.
- `NotificationEvent` and delivery behavior are unchanged on Desktop and are not a Cloud public-data concern.
- The existing `notice_source_relations` and content hashes remain the deduplication/update identity mechanism.

## Local development

From the repository root:

```powershell
docker compose -f docker-compose.cloud.yml up --build
```

Compose starts PostgreSQL, runs the migration once, then starts the Cloud API and Worker. The API is available at `http://127.0.0.1:8000`; PostgreSQL is exposed on port 5432 for local tools. The optional disposable test database is started with profile `test` on port 5433.

Development credentials in the compose file are local-only defaults. Production must inject a unique password/URL through deployment secrets and must not publish PostgreSQL directly.

## Future synchronization seam

Every notice exposes `created_at`, `updated_at`, and monotonic `version`. Phase 1.5 does not expose `/sync/notices`; a future endpoint can page by a stable `(updated_at, id)` cursor and use `version` to detect replacements without changing the public fact model.
