from __future__ import annotations

from hashlib import sha256

from app.services.normalization import canonicalize_url


def origin_item_key(native_id: str | None, url: str) -> str:
    """Return the source-scoped identity shared by Cloud and Local adapters."""

    normalized_native_id = (native_id or "").strip()
    if normalized_native_id:
        return f"native:{normalized_native_id}"
    canonical = canonicalize_url(url)
    return f"url:{sha256(canonical.encode('utf-8')).hexdigest()}"
