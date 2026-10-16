"""Classify a bounded attachment prefix; never claim a complete download."""
from __future__ import annotations

import re
from typing import Mapping

MIME_FAMILIES = {
    "application/pdf": {"pdf"}, "image/jpeg": {"jpg", "jpeg"}, "image/png": {"png"},
    "image/gif": {"gif"}, "image/webp": {"webp"},
    "application/zip": {"zip", "docx", "xlsx", "pptx"},
    "application/x-zip-compressed": {"zip", "docx", "xlsx", "pptx"},
    "application/msword": {"doc"}, "application/vnd.ms-excel": {"xls"}, "application/vnd.ms-powerpoint": {"ppt"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {"docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"xlsx"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {"pptx"},
    "application/x-rar-compressed": {"rar"}, "application/vnd.rar": {"rar"}, "application/x-7z-compressed": {"7z"},
}


def classify_attachment_prefix(status: int, headers: Mapping[str, str], prefix: bytes, expected_type: str = "") -> dict:
    result = {"category": "UNVERIFIED", "file_prefix_verified": False, "complete_download_verified": False,
              "read_bytes": len(prefix), "expected_type": expected_type.lower().lstrip(".")}
    def verdict(category, reason, **extra):
        return dict(result, category=category, reason=reason, **extra)
    if status in {401, 403, 429, 404, 410}:
        return verdict({401: "AUTH_REQUIRED", 403: "ACCESS_DENIED", 429: "RATE_LIMITED", 404: "NOT_FOUND", 410: "NOT_FOUND"}[status], f"HTTP {status}")
    if 300 <= status < 400:
        return verdict("REDIRECT_NOT_FOLLOWED", "Redirect is not file evidence")
    if status not in {200, 206}:
        return verdict("HTTP_ERROR", f"HTTP {status}")
    if not prefix:
        return verdict("EMPTY_RESPONSE", "No response bytes")
    content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), "").lower().split(";", 1)[0].strip()
    families = []
    if prefix.startswith(b"%PDF-"):
        families = ["pdf"]
    elif prefix.startswith(b"\xff\xd8\xff"):
        families = ["jpg", "jpeg"]
    elif prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        families = ["png"]
    elif prefix.startswith((b"GIF87a", b"GIF89a")):
        families = ["gif"]
    elif prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
        families = ["webp"]
    elif prefix.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        families = ["zip", "docx", "xlsx", "pptx"]
    elif prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        families = ["doc", "xls", "ppt"]
    elif prefix.startswith(b"Rar!\x1a\x07"):
        families = ["rar"]
    elif prefix.startswith(b"7z\xbc\xaf\x27\x1c"):
        families = ["7z"]
    if families:
        content_range = next((value for key, value in headers.items() if key.lower() == "content-range"), "")
        if status == 206 and content_range:
            match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", content_range.strip(), re.I)
            if not match or int(match[1]) != 0 or int(match[2]) < int(match[1]) or len(prefix) > int(match[2]) + 1 or (match[3] != "*" and int(match[2]) >= int(match[3])):
                return verdict("RANGE_RESPONSE_MISMATCH", "Response range does not establish a valid file prefix starting at byte zero")
        mime_family = MIME_FAMILIES.get(content_type)
        if content_type.startswith("text/") or content_type in {"application/xhtml+xml", "application/json"} or (mime_family is not None and not mime_family.intersection(families)):
            return verdict("HEADER_BODY_MISMATCH", "Binary signature conflicts with response content type", detected_family=families)
        if result["expected_type"] and result["expected_type"] not in families:
            return verdict("FILE_TYPE_MISMATCH", "Binary signature conflicts with link filename/type", detected_family=families)
        if result["expected_type"] and mime_family is not None and result["expected_type"] not in mime_family:
            return verdict("FILE_TYPE_MISMATCH", "Specific response MIME type conflicts with link filename/type", detected_family=families)
        return verdict("FILE_PREFIX_VERIFIED", "Recognized file/container prefix only; whole file and archive contents not checked",
                       file_prefix_verified=True, detected_family=families)
    try:
        text = prefix.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = prefix.decode("gb18030", errors="replace")
    if re.search(r"验证码|captcha|verifycode|challenge", text, re.I):
        return verdict("CAPTCHA_REQUIRED", "Verification page; no captcha submission or bypass")
    if re.search(r"type\s*=\s*['\"]?password|统一身份认证|用户登录", text, re.I):
        return verdict("AUTH_REQUIRED", "Login/authentication response")
    if re.search(r"仅限校内|校内网|校园网|校内IP|校内 IP", text, re.I):
        return verdict("ACCESS_RESTRICTED_PAGE", "Response describes campus-network access restrictions")
    if content_type in {"text/html", "application/xhtml+xml"} or re.match(r"\s*<(?:!doctype|html|head|body|script|form|div|p\b)", text, re.I):
        return verdict("DOWNLOAD_HTML_PAGE", "HTML instruction/error/download page, not file bytes")
    if content_type.startswith("text/") or result["expected_type"] in {"csv", "txt"}:
        return verdict("TEXT_FILE_UNVERIFIED", "Text has no decisive file signature; not promoted by status/disposition alone")
    return verdict("UNKNOWN_PREFIX", "No recognized file signature in bounded sample")
