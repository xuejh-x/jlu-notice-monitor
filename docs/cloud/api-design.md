# Cloud API Design

## Service boundary

The Cloud API runs as `app.cloud.main:app`. It is intentionally separate from the Desktop `app.main:app` so the public endpoint never exposes or mutates client-owned state.

Dates and timestamps use FastAPI's ISO-8601 JSON serialization. Missing values are `null`.

## `GET /api/notices`

Query parameters:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `page` | `1` | One-based page number |
| `limit` | `20` | Page size, 1–100 |
| `source` | — | Source code or numeric source ID |
| `importance` | — | Minimum importance score, 0–100 |
| `keyword` | — | Case-insensitive title/body match |

Example response:

```json
{
  "items": [
    {
      "id": 42,
      "source_id": 3,
      "title": "Example notice",
      "url": "https://example.edu/notice/42",
      "importance": 80,
      "deadline": "2026-10-01",
      "published_at": "2026-09-13",
      "created_at": "2026-09-13T02:30:00",
      "updated_at": "2026-09-13T02:30:00",
      "version": 1,
      "content_hash": "..."
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20,
  "total_pages": 1
}
```

`total` and `total_pages` are calculated after all filters and therefore define pagination over the current result set.

## `GET /api/notices/{id}`

Returns the list fields plus `content` and `attachments`. A missing or non-public notice returns HTTP 404.

```json
{
  "id": 42,
  "content": "Parsed notice body",
  "attachments": [
    {
      "id": 7,
      "filename": "guide.pdf",
      "url": "https://example.edu/guide.pdf",
      "hash": "...",
      "created_at": "2026-09-13T02:30:00"
    }
  ]
}
```

## `GET /api/sources`

Returns public, non-deleted sources:

```json
{
  "items": [
    {
      "id": 3,
      "name": "Computer Science",
      "url": "https://example.edu",
      "type": "official_adapter",
      "status": "healthy",
      "last_success_time": "2026-09-13T02:20:00",
      "created_at": "2026-09-01T00:00:00",
      "updated_at": "2026-09-13T02:20:00"
    }
  ]
}
```

## Health and security

`GET /health` performs a database query and is intended for container readiness checks. Phase 1.5 endpoints are read-only and public; production ingress should add TLS, request limits and observability. Authentication is intentionally deferred with the account system.

## Future endpoint compatibility

A future `GET /sync/notices?since=...` can reuse the same serialized fields. A cursor should include both `updated_at` and `id` so rows sharing a timestamp cannot be skipped. Client reconciliation should compare `version` and `content_hash`.
