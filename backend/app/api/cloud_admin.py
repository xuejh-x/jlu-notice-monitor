from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
import hmac
import json
from threading import Lock
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Source
from app.services.source_identity import source_identity
from app.services.source_security import UnsafeSourceUrl, validate_cloud_source_url
from app.sources.base import SourceError
from app.sources.generic import GenericPublicSource

router = APIRouter(prefix="/admin/sources", tags=["cloud-source-administration"])
_failed_attempts: dict[str, deque[datetime]] = defaultdict(deque)
_auth_lock = Lock()


class CloudSourceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    list_url: str = Field(min_length=8, max_length=2000)
    parser: Literal["auto", "generic_html", "rss", "atom"] = "auto"
    parser_config: dict[str, str | int | None] = Field(default_factory=dict)
    crawl_interval_seconds: int | None = Field(default=None, ge=900, le=86400)


class CloudPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cloud_policy: Literal["auto", "force_enabled", "force_disabled"]
    crawl_interval_seconds: int | None = Field(default=None, ge=900, le=86400)


def _admin_key_matches(provided: str, configured: str) -> bool:
    return hmac.compare_digest(provided.encode("utf-8"), configured.encode("utf-8"))


def _record_failed_attempt(address: str) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=1)
    with _auth_lock:
        bucket = _failed_attempts[address]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= get_settings().admin_auth_attempts_per_minute:
            raise HTTPException(status_code=429, detail="Too many failed administrator authentication attempts")
        bucket.append(now)


def require_admin_key(
    request: Request,
    provided: Annotated[str | None, Header(alias="X-Notice-Hub-Admin-Key")] = None,
) -> None:
    configured = (get_settings().admin_key or "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="Admin cloud promotion is not configured.")
    declared = int(request.headers.get("content-length", "0") or 0)
    if declared > 65_536:
        raise HTTPException(status_code=413, detail="Administrator request is too large")
    address = request.client.host if request.client else "unknown"
    if not provided:
        _record_failed_attempt(address)
        raise HTTPException(status_code=401, detail="Administrator key is required")
    if not _admin_key_matches(provided, configured):
        _record_failed_attempt(address)
        raise HTTPException(status_code=403, detail="Administrator authorization failed")


async def _cloud_preview(payload: CloudSourceDraft) -> tuple[str, list[dict[str, Any]]]:
    try:
        await validate_cloud_source_url(payload.list_url, allow_private_network=False)
    except UnsafeSourceUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    adapter = GenericPublicSource(
        {
            "code": "cloud-validation",
            "name": payload.name,
            "base_url": payload.list_url,
            "parser": payload.parser,
            "parser_config": payload.parser_config,
            "allow_private_network": False,
            "validation_scope": "cloud",
        }
    )
    try:
        notices = await adapter.fetch_list()
        preview = []
        for item in notices[:3]:
            detail = await adapter.fetch_detail(item)
            preview.append({"title": detail.title, "url": detail.url, "publish_date": detail.publish_date})
    except (SourceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Cloud source validation failed: {exc}") from exc
    finally:
        await adapter.close()
    if not preview:
        raise HTTPException(status_code=422, detail="Cloud source validation found no notices")
    return adapter.detected_type, preview


def _serialize(source: Source, *, reused: bool, preview: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cloud_source_id": source.code,
        "source_identity": source.source_identity,
        "name": source.name,
        "base_url": source.base_url,
        "source_scope": source.source_scope,
        "execution": source.execution,
        "cloud_policy": source.cloud_policy,
        "crawl_interval_seconds": source.crawl_interval_seconds,
        "reused": reused,
        "preview": preview,
    }


@router.post("/promote", dependencies=[Depends(require_admin_key)])
async def promote_cloud_source(payload: CloudSourceDraft, db: Session = Depends(get_db)) -> dict[str, Any]:
    identity = source_identity(payload.list_url)
    detected_type, preview = await _cloud_preview(payload)
    source = db.scalar(
        select(Source).where(
            Source.source_identity == identity,
            Source.execution == "cloud",
            Source.is_deleted.is_(False),
        )
    )
    reused = source is not None
    if source is None:
        code = f"shared-{identity[:16]}"
        source = Source(
            code=code,
            name=" ".join(payload.name.split()),
            base_url=payload.list_url,
            enabled=True,
            ownership="SHARED_CLOUD",
            source_type="public_feed" if detected_type in {"rss", "atom"} else "public_html",
            parser=detected_type,
            parser_config=json.dumps(payload.parser_config, ensure_ascii=False),
            subscribed=True,
            auth_type="none",
            health_state="unconfigured",
            source_identity=identity,
            cloud_source_id=code,
            source_scope="shared",
            execution="cloud",
            validation_status="passed",
            validated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(source)
    source.cloud_policy = "force_enabled"
    source.enabled = True
    source.crawl_interval_seconds = payload.crawl_interval_seconds
    source.validation_status = "passed"
    source.validated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(source)
    return _serialize(source, reused=reused, preview=preview)


@router.patch("/{cloud_source_id}/cloud-policy", dependencies=[Depends(require_admin_key)])
def update_cloud_policy(
    cloud_source_id: str,
    payload: CloudPolicyUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    source = db.scalar(
        select(Source).where(
            Source.code == cloud_source_id,
            Source.execution == "cloud",
            Source.is_deleted.is_(False),
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Cloud source not found")
    source.cloud_policy = payload.cloud_policy
    source.crawl_interval_seconds = payload.crawl_interval_seconds
    if payload.cloud_policy == "force_enabled":
        source.enabled = True
    db.commit()
    return _serialize(source, reused=True, preview=[])
