"""Verified TLS contexts for source HTTP clients, including frozen Windows apps."""
from __future__ import annotations

import os
import ssl
import sys

import certifi


def is_certificate_verification_error(error: BaseException) -> bool:
    """Recognize HTTPX/httpcore-wrapped SSL errors without localized text matching."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        current = current.__cause__ or current.__context__
    return False


def source_ssl_context(*, trust_env: bool = True) -> ssl.SSLContext:
    # Match HTTPX's explicit CA override precedence. Do not broaden a caller's
    # configured trust boundary, or silently fall back from a broken CA path.
    if trust_env:
        if cafile := os.environ.get("SSL_CERT_FILE"):
            return ssl.create_default_context(cafile=cafile)
        if capath := os.environ.get("SSL_CERT_DIR"):
            return ssl.create_default_context(capath=capath)

    if sys.platform == "win32":
        import truststore

        # CryptoAPI builds missing intermediates using Windows' cache/AIA and
        # verifies the chain, validity and hostname against trusted roots.
        # Keep certifi roots supported by the previous HTTPX default as well.
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=certifi.where())
        return context

    # Preserve the existing non-Windows / cloud trust policy.
    return ssl.create_default_context(cafile=certifi.where())
