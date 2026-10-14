"""Keep useful HTTP/SSL causes even when the outer exception has no message."""
from __future__ import annotations

import httpx

from app.services.tls import is_certificate_verification_error


def is_retryable_http_error(error: BaseException) -> bool:
    """Only retry transient transport/status failures within the caller's budget."""
    if is_certificate_verification_error(error):
        return False
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {502, 503, 504}
    return isinstance(error, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


def exception_summary(error: BaseException | None) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    while error is not None and id(error) not in seen and len(parts) < 8:
        seen.add(id(error))
        message = str(error).strip()
        parts.append(f"{type(error).__name__}: {message}" if message else repr(error))
        error = error.__cause__ or error.__context__
    summary = ""
    for part in parts:
        # SourceError may already contain the formatted cause while also
        # retaining it via `raise ... from ...`.
        if part not in summary:
            summary = f"{summary} <- {part}" if summary else part
    return summary or "UnknownError"
