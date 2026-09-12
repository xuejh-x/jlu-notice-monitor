from __future__ import annotations

from hashlib import sha256
import posixpath
from typing import Literal
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from app.services.normalization import TRACKING_PARAMS

ExecutionPolicy = Literal["cloud_only", "cloud_preferred", "local_only"]


def default_execution_policy(ownership: str) -> ExecutionPolicy:
    if ownership == "OFFICIAL_CLOUD":
        return "cloud_preferred"
    if ownership == "SHARED_CLOUD":
        return "cloud_only"
    return "local_only"


def canonicalize_source_url(url: str) -> str:
    """Canonical URL used only for source identity, not for display or fetching."""

    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = quote(posixpath.normpath(parts.path or "/"), safe="/%:@")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMS
        ),
        doseq=True,
    )
    return urlunsplit((scheme, host, path, query, ""))


def source_identity(url: str) -> str:
    return sha256(canonicalize_source_url(url).encode("utf-8")).hexdigest()


def resolve_cloud_execution(*, execution: str, cloud_policy: str, enabled: bool) -> bool:
    if execution != "cloud":
        return False
    if cloud_policy == "force_enabled":
        return True
    if cloud_policy == "force_disabled":
        return False
    return enabled
