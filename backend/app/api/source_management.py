from __future__ import annotations

import hashlib
import httpx
import json
import secrets
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crawler import crawler_manager
from app.crawler.runner import CrawlerAlreadyRunning
from app.database import get_db
from app.models import Source
from app.paths import get_auth_profile_dir
from app.services.credentials import CredentialStorageUnavailable, credential_store
from app.services.source_identity import source_identity
from app.services.source_security import UnsafeSourceUrl, validate_source_url, validate_url_syntax
from app.sources.base import SourceError
from app.sources.generic import GenericPublicSource

router = APIRouter(prefix="/source-config", tags=["source-configuration"])


class ParserConfiguration(BaseModel):
    item_selector: str | None = Field(default=None, max_length=500)
    title_selector: str | None = Field(default=None, max_length=500)
    link_selector: str | None = Field(default=None, max_length=500)
    date_selector: str | None = Field(default=None, max_length=500)
    content_selector: str | None = Field(default=None, max_length=500)
    attachment_selector: str | None = Field(default=None, max_length=500)
    next_page_selector: str | None = Field(default=None, max_length=500)
    pagination_limit: int = Field(default=1, ge=1, le=3)


AuthType = Literal[
    "none",
    "username_password",
    "browser_session",
    "cookie",
    "basic",
    "bearer",
    "api_token",
    "custom_adapter",
]


class SourceDraft(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    list_url: str = Field(min_length=8, max_length=2000)
    kind: Literal["public", "private"] = "public"
    parser: Literal["auto", "generic_html", "rss", "atom"] = "auto"
    parser_config: ParserConfiguration = Field(default_factory=ParserConfiguration)
    auth_type: AuthType = "none"
    login_url: str | None = Field(default=None, max_length=2000)
    username: str | None = Field(default=None, max_length=300)
    password: str | None = Field(default=None, max_length=2000)
    remember_credentials: bool = False
    allow_private_network: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("source name cannot be blank")
        return cleaned


class SourceCreate(SourceDraft):
    preview_token: str


class SourceEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    list_url: str | None = Field(default=None, min_length=8, max_length=2000)
    parser: Literal["auto", "generic_html", "rss", "atom"] | None = None
    parser_config: ParserConfiguration | None = None
    login_url: str | None = Field(default=None, max_length=2000)
    username: str | None = Field(default=None, max_length=300)
    password: str | None = Field(default=None, max_length=2000)
    remember_credentials: bool | None = None
    allow_private_network: bool | None = None
    preview_token: str | None = None


class EnableRequest(BaseModel):
    enabled: bool
    authentication_warning_acknowledged: bool = False


class SubscriptionRequest(BaseModel):
    subscribed: bool


class DeleteRequest(BaseModel):
    clear_local_login: bool = False


class PromotionRequest(BaseModel):
    admin_key: str = Field(min_length=1, max_length=4096)
    crawl_interval_seconds: int | None = Field(default=None, ge=900, le=86400)


class CloudPolicyRequest(PromotionRequest):
    cloud_policy: Literal["auto", "force_enabled", "force_disabled"]


_preview_tokens: dict[str, tuple[str, datetime]] = {}


def _fingerprint(draft: SourceDraft) -> str:
    value = draft.model_dump(exclude={"password", "remember_credentials"})
    value["has_password"] = bool(draft.password)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _issue_preview_token(draft: SourceDraft) -> str:
    now = datetime.now(UTC)
    for token, (_, expires) in list(_preview_tokens.items()):
        if expires < now:
            _preview_tokens.pop(token, None)
    token = secrets.token_urlsafe(24)
    _preview_tokens[token] = (_fingerprint(draft), now + timedelta(minutes=10))
    return token


def _consume_preview_token(token: str, draft: SourceDraft) -> None:
    value = _preview_tokens.pop(token, None)
    if value is None or value[1] < datetime.now(UTC) or value[0] != _fingerprint(draft):
        raise HTTPException(status_code=409, detail="A successful matching preview is required")


def _serialize_source(source: Source) -> dict[str, Any]:
    return {
        "id": source.id,
        "code": source.code,
        "name": source.name,
        "base_url": source.base_url,
        "ownership": source.ownership,
        "source_type": source.source_type,
        "parser": source.parser,
        "parser_config": json.loads(source.parser_config or "{}"),
        "subscribed": source.subscribed,
        "enabled": source.enabled,
        "auth_type": source.auth_type,
        "username": source.auth_username,
        "password_saved": bool(source.credential_ref),
        "login_url": source.login_url,
        "allow_private_network": source.allow_private_network,
        "health_state": source.health_state,
        "last_error_code": source.last_error_code,
        "last_error": source.last_error,
        "last_checked_at": source.last_checked_at,
        "last_success_at": source.last_success_at,
        "requires_reauthentication": source.health_state == "needs_reauth",
        "source_identity": source.source_identity,
        "cloud_source_id": source.cloud_source_id,
        "source_scope": source.source_scope,
        "execution": source.execution,
        "cloud_policy": source.cloud_policy,
        "crawl_interval_seconds": source.crawl_interval_seconds,
        "validation_status": source.validation_status,
        "validated_at": source.validated_at,
    }


@router.get("")
def list_source_configuration(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Source).where(Source.is_deleted.is_(False)).order_by(Source.id)).all()
    return [_serialize_source(source) for source in rows]


@router.post("/preview")
async def preview_source(draft: SourceDraft) -> dict[str, Any]:
    if draft.kind == "public" and draft.auth_type != "none":
        raise HTTPException(status_code=422, detail="Public sources cannot contain authentication configuration")
    if draft.kind == "private" and draft.auth_type == "none":
        raise HTTPException(status_code=422, detail="Private sources require an authentication type")
    try:
        validate_url_syntax(draft.list_url)
        if draft.login_url:
            validate_url_syntax(draft.login_url)
        await validate_source_url(
            draft.list_url,
            allow_private_network=draft.kind == "private" and draft.allow_private_network,
        )
    except UnsafeSourceUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if draft.kind == "private" and draft.auth_type in {
        "username_password", "browser_session", "cookie", "custom_adapter"
    }:
        return {
            "status": "authentication_required",
            "detected_type": draft.parser,
            "found": 0,
            "items": [],
            "message": "Complete the local login flow before parser verification.",
            "preview_token": _issue_preview_token(draft),
        }
    adapter = GenericPublicSource(
        {
            "code": "preview",
            "name": draft.name,
            "base_url": draft.list_url,
            "parser": draft.parser,
            "parser_config": draft.parser_config.model_dump(exclude_none=True),
            "allow_private_network": draft.kind == "private" and draft.allow_private_network,
        }
    )
    if draft.kind == "private" and draft.password:
        if draft.auth_type == "basic":
            import base64

            token = base64.b64encode(f"{draft.username or ''}:{draft.password}".encode("utf-8")).decode("ascii")
            adapter.fetcher.client.headers["Authorization"] = f"Basic {token}"
        elif draft.auth_type in {"bearer", "api_token"}:
            adapter.fetcher.client.headers["Authorization"] = f"Bearer {draft.password}"
        elif draft.auth_type == "cookie":
            adapter.fetcher.client.headers["Cookie"] = draft.password
    try:
        notices = await adapter.fetch_list()
        preview = []
        for item in notices[:3]:
            detail = await adapter.fetch_detail(item)
            preview.append(
                {
                    "title": detail.title,
                    "url": detail.url,
                    "publish_date": detail.publish_date,
                    "content_preview": detail.content[:240],
                }
            )
    except (SourceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Source preview failed: {exc}") from exc
    finally:
        await adapter.close()
    if not preview:
        raise HTTPException(status_code=422, detail="Source preview did not find parseable notices")
    return {
        "status": "success",
        "detected_type": adapter.detected_type,
        "found": len(notices),
        "items": preview,
        "preview_token": _issue_preview_token(draft),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    draft = SourceDraft(**payload.model_dump(exclude={"preview_token"}))
    _consume_preview_token(payload.preview_token, draft)
    code = f"local-{uuid4().hex[:12]}"
    is_private = draft.kind == "private"
    source = Source(
        code=code,
        name=draft.name,
        base_url=draft.list_url,
        enabled=not is_private,
        ownership="CUSTOM_LOCAL_PRIVATE" if is_private else "CUSTOM_LOCAL_PUBLIC",
        source_type="private_browser" if is_private and draft.auth_type == "browser_session" else (
            "private_http" if is_private else "public_feed" if draft.parser in {"rss", "atom"} else "public_html"
        ),
        parser=draft.parser,
        parser_config=json.dumps(draft.parser_config.model_dump(exclude_none=True), ensure_ascii=False),
        subscribed=True,
        auth_type=draft.auth_type,
        auth_username=draft.username,
        login_url=draft.login_url,
        session_profile_ref=f"auth-profiles/{code}" if is_private else None,
        allow_private_network=is_private and draft.allow_private_network,
        health_state="needs_reauth" if is_private else "unconfigured",
        source_identity=source_identity(draft.list_url),
        source_scope="private" if is_private else "personal",
        execution="local",
        validation_status="passed",
        validated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    if is_private and draft.remember_credentials and draft.password:
        reference = f"source-{code}"
        try:
            credential_store.save(reference, draft.password)
        except CredentialStorageUnavailable as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        source.credential_ref = reference
    db.add(source)
    db.commit()
    db.refresh(source)
    return _serialize_source(source)


@router.patch("/{source_id}")
def edit_source(source_id: int, payload: SourceEdit, db: Session = Depends(get_db)) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None or source.is_deleted or source.ownership in {"OFFICIAL_CLOUD", "SHARED_CLOUD"}:
        raise HTTPException(status_code=404, detail="Custom source not found")
    values = payload.model_dump(exclude_unset=True)
    parser_change = any(key in values for key in ("list_url", "parser", "parser_config"))
    if parser_change and not payload.preview_token:
        raise HTTPException(status_code=409, detail="A successful preview is required before parser changes")
    if parser_change:
        current_parser_config = ParserConfiguration(**json.loads(source.parser_config or "{}"))
        draft = SourceDraft(
            name=payload.name or source.name,
            list_url=payload.list_url or source.base_url,
            kind="private" if source.ownership == "CUSTOM_LOCAL_PRIVATE" else "public",
            parser=payload.parser or source.parser,
            parser_config=payload.parser_config or current_parser_config,
            auth_type=source.auth_type,
            login_url=payload.login_url if "login_url" in values else source.login_url,
            username=payload.username if "username" in values else source.auth_username,
            password=payload.password,
            remember_credentials=bool(payload.remember_credentials),
            allow_private_network=(
                bool(payload.allow_private_network)
                if "allow_private_network" in values
                else source.allow_private_network
            ),
        )
        assert payload.preview_token is not None
        _consume_preview_token(payload.preview_token, draft)
    if "name" in values:
        source.name = " ".join(str(values["name"]).split())
    if "list_url" in values:
        source.base_url = validate_url_syntax(str(values["list_url"]))
        source.source_identity = source_identity(source.base_url)
    if "parser" in values:
        source.parser = str(values["parser"])
    if "parser_config" in values and values["parser_config"] is not None:
        config = payload.parser_config
        assert config is not None
        source.parser_config = json.dumps(config.model_dump(exclude_none=True), ensure_ascii=False)
    if parser_change:
        source.validation_status = "passed"
        source.validated_at = datetime.now(UTC).replace(tzinfo=None)
    if "login_url" in values:
        source.login_url = validate_url_syntax(payload.login_url) if payload.login_url else None
    if "username" in values:
        source.auth_username = payload.username
    if "allow_private_network" in values:
        source.allow_private_network = bool(payload.allow_private_network) and source.ownership == "CUSTOM_LOCAL_PRIVATE"
    if payload.remember_credentials and payload.password:
        reference = source.credential_ref or f"source-{source.code}"
        try:
            credential_store.save(reference, payload.password)
        except CredentialStorageUnavailable as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        source.credential_ref = reference
    elif payload.remember_credentials is False and source.credential_ref:
        credential_store.delete(source.credential_ref)
        source.credential_ref = None
    db.commit()
    db.refresh(source)
    return _serialize_source(source)


@router.post("/{source_id}/subscription")
def update_subscription(source_id: int, payload: SubscriptionRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None or source.is_deleted or source.ownership not in {"OFFICIAL_CLOUD", "SHARED_CLOUD"}:
        raise HTTPException(status_code=404, detail="Cloud source not found")
    source.subscribed = payload.subscribed
    db.commit()
    return _serialize_source(source)


@router.post("/{source_id}/enabled")
def update_enabled(source_id: int, payload: EnableRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None or source.is_deleted or source.ownership in {"OFFICIAL_CLOUD", "SHARED_CLOUD"}:
        raise HTTPException(status_code=404, detail="Custom source not found")
    is_private = source.ownership == "CUSTOM_LOCAL_PRIVATE"
    if payload.enabled and is_private and not payload.authentication_warning_acknowledged:
        raise HTTPException(status_code=409, detail="Authentication warning acknowledgement is required")
    source.enabled = payload.enabled
    if not payload.enabled:
        source.health_state = "disabled"
    elif is_private and source.health_state != "authenticated":
        source.health_state = (
            "authenticated"
            if source.auth_type in {"basic", "bearer", "api_token", "cookie"} and source.credential_ref
            else "needs_reauth"
        )
    else:
        source.health_state = "unconfigured"
    db.commit()
    return _serialize_source(source)


@router.post("/{source_id}/check", status_code=status.HTTP_202_ACCEPTED)
def check_source(source_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    source = db.get(Source, source_id)
    if source is None or source.is_deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.enabled or source.health_state == "needs_reauth":
        raise HTTPException(status_code=409, detail="Source is paused or requires reauthentication")
    try:
        crawler_manager.start(source.code, trigger="manual")
    except CrawlerAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "started", "source": source.code}


@router.post("/{source_id}/reauthenticate")
def reauthenticate(source_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None or source.is_deleted or source.ownership != "CUSTOM_LOCAL_PRIVATE":
        raise HTTPException(status_code=404, detail="Private source not found")
    source.health_state = "needs_reauth"
    source.reauth_notified_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return {
        "status": "manual_login_required",
        "source_id": source.id,
        "auth_type": source.auth_type,
        "login_url": source.login_url or source.base_url,
        "message": "Complete CAPTCHA, MFA, QR, or SSO manually. Notice Hub will not bypass it.",
    }


def _cloud_admin_endpoint(path: str) -> str:
    settings = get_settings()
    base = (settings.cloud_admin_url or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="Cloud source administration is not configured.")
    if not base.startswith("https://"):
        local_fixture = settings.environment in {"test", "development"} and base.startswith(
            ("http://127.0.0.1", "http://localhost")
        )
        if not local_fixture:
            raise HTTPException(status_code=503, detail="Cloud source administration requires HTTPS.")
    return f"{base}/{path.lstrip('/')}"


async def _call_cloud_admin(
    method: str,
    path: str,
    admin_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(
            timeout=get_settings().request_timeout,
            follow_redirects=False,
        ) as client:
            response = await client.request(
                method,
                _cloud_admin_endpoint(path),
                headers={"X-Notice-Hub-Admin-Key": admin_key},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Cloud source administration is unavailable") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Cloud source administration returned an invalid response",
        ) from exc
    if response.status_code >= 400:
        detail = body.get("detail") if isinstance(body, dict) else None
        raise HTTPException(
            status_code=response.status_code,
            detail=detail or "Cloud source administration failed",
        )
    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="Cloud source administration returned an invalid response")
    return body


@router.post("/{source_id}/promote")
async def promote_source(
    source_id: int,
    payload: PromotionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if source is None or source.is_deleted or source.ownership != "CUSTOM_LOCAL_PUBLIC":
        raise HTTPException(status_code=404, detail="Eligible local public source not found")
    if source.validation_status != "passed" or source.validated_at is None:
        raise HTTPException(
            status_code=409,
            detail="A successful source test and preview is required before promotion",
        )
    response = await _call_cloud_admin(
        "POST",
        "/api/admin/sources/promote",
        payload.admin_key,
        {
            "name": source.name,
            "list_url": source.base_url,
            "parser": source.parser,
            "parser_config": json.loads(source.parser_config or "{}"),
            "crawl_interval_seconds": payload.crawl_interval_seconds,
        },
    )
    cloud_source_id = str(response.get("cloud_source_id") or "")
    identity = str(response.get("source_identity") or "")
    if not cloud_source_id or len(identity) != 64:
        raise HTTPException(
            status_code=502,
            detail="Cloud source administration returned incomplete identity data",
        )
    source.cloud_source_id = cloud_source_id
    source.source_identity = identity
    source.ownership = "SHARED_CLOUD"
    source.source_scope = "shared"
    source.execution = "cloud"
    source.cloud_policy = "force_enabled"
    source.crawl_interval_seconds = response.get("crawl_interval_seconds")
    source.subscribed = True
    source.enabled = True
    source.health_state = "unconfigured"
    db.commit()
    db.refresh(source)
    result = _serialize_source(source)
    result["promotion_reused"] = bool(response.get("reused"))
    return result


@router.post("/{source_id}/cloud-policy")
async def set_cloud_policy(
    source_id: int,
    payload: CloudPolicyRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if (
        source is None
        or source.is_deleted
        or source.ownership != "SHARED_CLOUD"
        or not source.cloud_source_id
    ):
        raise HTTPException(status_code=404, detail="Shared cloud source not found")
    response = await _call_cloud_admin(
        "PATCH",
        f"/api/admin/sources/{source.cloud_source_id}/cloud-policy",
        payload.admin_key,
        {
            "cloud_policy": payload.cloud_policy,
            "crawl_interval_seconds": payload.crawl_interval_seconds,
        },
    )
    source.cloud_policy = str(response.get("cloud_policy") or payload.cloud_policy)
    source.crawl_interval_seconds = response.get("crawl_interval_seconds")
    db.commit()
    db.refresh(source)
    return _serialize_source(source)


@router.delete("/{source_id}")
def delete_source(source_id: int, payload: DeleteRequest, db: Session = Depends(get_db)) -> dict[str, bool]:
    source = db.get(Source, source_id)
    if source is None or source.is_deleted or source.ownership in {"OFFICIAL_CLOUD", "SHARED_CLOUD"}:
        raise HTTPException(status_code=404, detail="Custom source not found")
    source.enabled = False
    source.is_deleted = True
    source.health_state = "disabled"
    if payload.clear_local_login:
        if source.credential_ref:
            credential_store.delete(source.credential_ref)
            source.credential_ref = None
        settings = get_settings()
        profile = get_auth_profile_dir(source.code, settings.environment, settings.app_data_dir).resolve()
        parent = profile.parent.resolve()
        if profile.parent == parent and profile != parent and parent in profile.parents and profile.exists():
            shutil.rmtree(profile)
    db.commit()
    return {"deleted": True, "local_login_cleared": payload.clear_local_login}
