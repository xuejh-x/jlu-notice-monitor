from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import AppState
from app.schemas.notice import AttachmentData, NoticeCandidate
from app.sources.base import NoticeSource, SourceError


class CloudFeedSource(NoticeSource):
    """Read-only official feed adapter used only by Desktop deployments."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        feed_url = str(config.get("public_feed_url") or get_settings().public_feed_url or "").strip()
        if not feed_url:
            raise SourceError("PUBLIC_FEED_NOT_CONFIGURED")
        self.feed_url = feed_url.rstrip("/") + "/"
        self.client = httpx.AsyncClient(timeout=get_settings().request_timeout, follow_redirects=False)
        self.cloud_source_id = str(config.get("cloud_source_id") or self.code)
        self._cursor_key = f"cloud-feed-cursor:{self.cloud_source_id}"

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

    async def fetch_list(self) -> list[NoticeCandidate]:
        updated_after, after_id = self._load_cursor()
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
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise SourceError(f"PUBLIC_FEED_UNAVAILABLE: {type(exc).__name__}") from exc
            if payload.get("version") != "1" or not isinstance(payload.get("items"), list):
                raise SourceError("PUBLIC_FEED_INVALID_RESPONSE")
            for item in payload["items"]:
                results.append(
                    NoticeCandidate(
                        public_id=item["public_id"],
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
        return results

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        return notice

    async def close(self) -> None:
        await self.client.aclose()
