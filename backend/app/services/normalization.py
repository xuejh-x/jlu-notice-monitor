from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def normalize_title(title: str) -> str:
    value = normalize_whitespace(title).lower()
    value = re.sub(
        r"^\s*[\[【(（]\s*(?:转发|通知|公告|公示|转载|置顶)\s*[\]】)）]\s*",
        "",
        value,
    )
    value = re.sub(r"(?:关于|转发[：:]?|通知|公告|公示)", "", value)
    value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)
    return value


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMS])
    path = re.sub(r"/{2,}", "/", parts.path)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def content_hash(title: str, content: str) -> str:
    stable = normalize_whitespace(f"{title}\n{content}")
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()
