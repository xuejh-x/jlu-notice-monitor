# Cloud Database Design

## Design principles

PostgreSQL stores public, user-independent facts. Read state, favorites, settings and local delivery state remain on clients. The Cloud schema reuses the established SQLAlchemy fact entities so the crawler and deduplication pipeline do not fork.

Conceptual names in this document map to the repository's existing plural table names.

## `sources`

Core platform mapping:

| Platform field | Existing field | Purpose |
| --- | --- | --- |
| `id` | `id` | Stable integer identity |
| `name` | `name` | Display name |
| `url` | `base_url` | Source root URL |
| `type` | `source_type` | Adapter/source type |
| `status` | `health_state` | Source health |
| `last_success_time` | `last_success_at` | Last successful crawl |
| `created_at` | `created_at` | Creation time |
| `updated_at` | `updated_at` | Last metadata change |

The existing `code`, parser metadata, ownership, execution policy and health fields remain available to the Worker. Only non-deleted `OFFICIAL_CLOUD` and `SHARED_CLOUD` sources are exposed by the Cloud API.

## `notices`

| Platform field | Existing field | Notes |
| --- | --- | --- |
| `id` | `id` | Preserved during SQLite migration |
| `source_id` | `source_id` | Primary public source |
| `title` | `title` | Notice title |
| `content` | `content` | Parsed body, detail endpoint only |
| `url` | `url` | Canonical user-facing location |
| `importance` | `importance_score` | 0–100 computed score |
| `deadline` | `registration_deadline` | Registration deadline when known |
| `published_at` | `publish_date` | Source publication date |
| `created_at` | `first_seen_at` | First observed time |
| `updated_at` | `updated_at` | Last content update |
| `content_hash` | `content_hash` | Deduplication/change detection hash |
| `version` | `version` | Starts at 1 and increments on UPDATED |

The existing category, parsed dates, target audience and source relation metadata are preserved because Desktop and the current crawler use them. `notice_source_relations` provides per-source URL, identity key and content hash, allowing one logical notice to keep source-specific observations.

## `attachments`

| Platform field | Existing field | Notes |
| --- | --- | --- |
| `id` | `id` | Stable attachment identity |
| `notice_id` | `notice_id` | Cascading notice foreign key |
| `filename` | `filename` | Display filename |
| `url` | `url` | Download/source URL |
| `hash` | `content_hash` | Metadata identity hash |
| `created_at` | `created_at` | First stored time |

The existing unique constraint on `(notice_id, url)` makes repeated crawls idempotent. Attachment rows cascade with their notice.

## Supporting Cloud tables

- `notice_source_relations`: source-scoped deduplication and last-seen metadata.
- `notice_updates`: immutable old/new hash change records.
- `importance_rules`: existing rule-based importance scorer configuration.
- `app_state`: scheduler/retention operational timestamps.

The initial Cloud migration intentionally does not create `user_states`, `favorites`, `notification_preferences`, `notification_events`, or `notification_deliveries`.

## Consistency and deletion

All notice-owned relations use foreign keys with cascading deletion where already defined. The 365-day Cloud retention task deletes public notices by age; attachments, source relations and update records follow their existing ownership rules. Source definitions are never deleted by notice cleanup.
