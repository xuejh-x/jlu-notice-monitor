from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import AppState
from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.notice_identity import origin_item_key
from app.sources.base import NoticeSource, SourceError

PUBLIC_FEED_NOT_CONFIGURED = "PUBLIC_FEED_NOT_CONFIGURED"
PUBLIC_FEED_UNAVAILABLE = "PUBLIC_FEED_UNAVAILABLE"
PUBLIC_FEED_NETWORK_ERROR = "PUBLIC_FEED_NETWORK_ERROR"
PUBLIC_FEED_TIMEOUT = "PUBLIC_FEED_TIMEOUT"
PUBLIC_FEED_HTTP_ERROR = "PUBLIC_FEED_HTTP_ERROR"
PUBLIC_FEED_INVALID_RESPONSE = "PUBLIC_FEED_INVALID_RESPONSE"
PUBLIC_FEED_EXPIRED = "PUBLIC_FEED_EXPIRED"


def is_public_feed_not_configured(last_error_code: str | None, last_error: str | None) -> bool:
    return last_error_code == PUBLIC_FEED_NOT_CONFIGURED or bool(
        last_error and PUBLIC_FEED_NOT_CONFIGURED in last_error
    )


class CloudFeedSource(NoticeSource):
    """Read-only official feed adapter used only by Desktop deployments."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        feed_url = str(config.get("public_feed_url") or get_settings().public_feed_url or "").strip()
        if not feed_url:
            raise SourceError(PUBLIC_FEED_NOT_CONFIGURED)
        self.feed_url = feed_url.rstrip("/") + "/"
        self.client = httpx.AsyncClient(timeout=get_settings().request_timeout, follow_redirects=False)
        self.cloud_source_id = str(config.get("cloud_source_id") or self.code)
        self._cursor_key = f"cloud-feed-cursor:{self.cloud_source_id}"
        self._baseline_key = f"cloud-feed-baseline:{self.cloud_source_id}"
        # The first feed import is a migration of public facts, not a stream of
        # user-facing arrivals.  The runner uses this signal to establish a
        # local baseline before it creates notification events.
        self.initial_sync = False

    def _load_cursor(self) -> tuple[str | None, int]:
        with SessionLocal() as db:
            row = db.get(AppState, self._cursor_key)
            if row is None or not row.value:
                return None, 0
            timestamp, _, raw_id = row.value.partition("|")
            return timestamp or None, int(raw_id or 0)

    def _save_cursor(self, updated_at: str, after_id: int) -> None:
        with SessionLocal() as db:
            row = db.get(AppState, self._cursor_key) or AppState(key=self._cursor_key)
            row.value = f"{updated_at}|{after_id}"
            db.add(row)
            db.commit()

    def _has_baseline(self) -> bool:
        with SessionLocal() as db:
            return db.get(AppState, self._baseline_key) is not None

    def _save_baseline(self) -> None:
        with SessionLocal() as db:
            db.add(AppState(key=self._baseline_key, value="established"))
            db.commit()

    async def fetch_list(self) -> list[NoticeCandidate]:
        updated_after, after_id = self._load_cursor()
        self.initial_sync = not self._has_baseline()
        results: list[NoticeCandidate] = []
        max_pages = get_settings().source_max_pages
        for _ in range(max_pages):
            params: dict[str, Any] = {"source": self.cloud_source_id, "page_size": 100}
            if updated_after:
                params.update(updated_after=updated_after, after_id=after_id)
            try:
                response = await self.client.get(urljoin(self.feed_url, "notices"), params=params)
                response.raise_for_status()
                payload = response.json()
            except httpx.TimeoutException as exc:
                raise SourceError(f"{PUBLIC_FEED_UNAVAILABLE}:{PUBLIC_FEED_TIMEOUT}") from exc
            except httpx.HTTPStatusError as exc:
                raise SourceError(
                    f"{PUBLIC_FEED_UNAVAILABLE}:{PUBLIC_FEED_HTTP_ERROR}:{exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise SourceError(f"{PUBLIC_FEED_UNAVAILABLE}:{PUBLIC_FEED_NETWORK_ERROR}") from exc
            except (ValueError, TypeError) as exc:
                raise SourceError(PUBLIC_FEED_INVALID_RESPONSE) from exc
            if payload.get("version") != "1" or not isinstance(payload.get("items"), list):
                raise SourceError(PUBLIC_FEED_INVALID_RESPONSE)
            self._validate_freshness(payload)
            for item in payload["items"]:
                results.append(
                    NoticeCandidate(
                        public_id=item["public_id"],
                        origin_item_key=item.get("origin_item_key") or origin_item_key(None, item["url"]),
                        title=item["title"],
                        url=item["url"],
                        publish_date=item.get("publish_date"),
                        publisher=item.get("publisher"),
                        content=item.get("content") or "",
                        attachments=[AttachmentData(**attachment) for attachment in item.get("attachments", [])],
                        category=item.get("category"),
                        registration_start=item.get("registration_start"),
                        registration_deadline=item.get("registration_deadline"),
                        event_start=item.get("event_start"),
                        event_end=item.get("event_end"),
                        target_students=item.get("target_students"),
                        registration_method=item.get("registration_method"),
                        competition_level=item.get("competition_level"),
                    )
                )
            next_cursor = payload.get("next")
            if not next_cursor:
                break
            updated_after = str(next_cursor["updated_after"])
            after_id = int(next_cursor["after_id"])
            if not payload.get("has_more"):
                break
        if updated_after:
            # The cursor advances only after every accepted page was parsed.
            datetime.fromisoformat(updated_after.replace("Z", "+00:00"))
            self._save_cursor(updated_after, after_id)
        if self.initial_sync:
            # An empty successful first response also establishes a baseline:
            # notices arriving on a later poll are genuinely new.
            self._save_baseline()
        return results

    @staticmethod
    def _validate_freshness(payload: dict[str, Any]) -> None:
        # Older v1 feeds did not expose freshness metadata. They remain compatible;
        # upgraded feeds make an explicit missing/stale timestamp fallback-eligible.
        if "source_last_success_at" not in payload:
            return
        raw = payload.get("source_last_success_at")
        if not raw:
            raise SourceError(PUBLIC_FEED_EXPIRED)
        try:
            last_success = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError as exc:
            raise SourceError(PUBLIC_FEED_INVALID_RESPONSE) from exc
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=UTC)
        else:
            last_success = last_success.astimezone(UTC)
        stale_after = timedelta(seconds=get_settings().cloud_feed_stale_after_seconds)
        if datetime.now(UTC) - last_success > stale_after:
            raise SourceError(PUBLIC_FEED_EXPIRED)

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        return notice

    async def close(self) -> None:
        await self.client.aclose()
