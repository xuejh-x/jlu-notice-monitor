from __future__ import annotations

import ssl
from pathlib import Path

import httpx
import pytest

from app.parsers import parse_list_html
from app.schemas.notice import NoticeCandidate
from app.sources.base import SourceError, StaticHTMLSource
from app.sources.generic import SafeFetcher, parse_configured_html


@pytest.fixture
def client_factory(monkeypatch):
    async def allow(url, **kwargs):
        return url
    monkeypatch.setattr("app.sources.generic.validate_source_url", allow)

    async def create(kind, handler):
        if kind == "generic":
            source = SafeFetcher(transport=httpx.MockTransport(handler))
            get = source.get
        else:
            source = StaticHTMLSource({"code": "fixture", "name": "Fixture", "base_url": "https://fixture.test"})
            await source.client.aclose()
            source.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
            get = source._get
        source.retries = 2
        source.backoff = 0
        return source, get
    return create


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["generic", "static"])
@pytest.mark.parametrize("status", [401, 403, 404, 410, 429, 500, 501])
async def test_deterministic_http_errors_are_not_retried(kind, status, client_factory):
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(status, text="blocked")
    source, get = await client_factory(kind, respond)
    try:
        with pytest.raises(SourceError, match=str(status)):
            await get("https://fixture.test/notice")
        assert len(calls) == 1
    finally:
        await source.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["generic", "static"])
@pytest.mark.parametrize("mode", ["502", "503", "504", "timeout", "eof"])
async def test_transient_failure_recovers_with_existing_retry_budget(kind, mode, client_factory):
    calls = []
    def respond(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            if mode == "timeout":
                raise httpx.ReadTimeout("", request=request)
            if mode == "eof":
                error = httpx.ConnectError("", request=request)
                error.__cause__ = ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING")
                raise error
            return httpx.Response(int(mode), text="temporary failure")
        return httpx.Response(200, text="recovered")
    source, get = await client_factory(kind, respond)
    try:
        result = await get("https://fixture.test/notice")
        assert (result[0] if kind == "generic" else result) == "recovered"
        assert len(calls) == 2 and source.retries == 2
    finally:
        await source.close()


@pytest.mark.asyncio
async def test_generic_retry_restarts_original_url_and_revalidates_each_hop(client_factory, monkeypatch):
    calls, validated = [], []
    async def allow(url, **kwargs):
        validated.append(url)
        return url
    monkeypatch.setattr("app.sources.generic.validate_source_url", allow)
    def respond(request):
        calls.append(request.url.path)
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/first" if calls.count("/start") == 1 else "/fresh"})
        if request.url.path == "/first":
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, text="fresh target")
    source, get = await client_factory("generic", respond)
    try:
        body, _, final = await get("https://fixture.test/start")
        assert calls == ["/start", "/first", "/start", "/fresh"]
        assert [httpx.URL(url).path for url in validated] == calls
        assert body == "fresh target" and final.endswith("/fresh")
    finally:
        await source.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["loop", "missing_location", "size"])
async def test_generic_policy_failures_do_not_restart_request_chain(mode, client_factory):
    calls = []
    def respond(request):
        calls.append(str(request.url))
        if mode == "loop":
            return httpx.Response(308, headers={"location": "/loop"})
        if mode == "missing_location":
            return httpx.Response(302)
        return httpx.Response(200, content=b"too large", headers={"content-length": "999999999"})
    source, get = await client_factory("generic", respond)
    try:
        with pytest.raises(SourceError):
            await get("https://fixture.test/start")
        assert len(calls) == (source.max_redirects + 1 if mode == "loop" else 1)
    finally:
        await source.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["generic", "static"])
async def test_certificate_failure_keeps_cause_and_stops(kind, client_factory):
    calls = []
    def respond(request):
        calls.append(request)
        error = httpx.ConnectError("", request=request)
        error.__cause__ = ssl.SSLCertVerificationError(1, "expired")
        raise error
    source, get = await client_factory(kind, respond)
    try:
        with pytest.raises(SourceError, match="TLS_CERTIFICATE_VERIFY_FAILED") as caught:
            await get("https://fixture.test/notice")
        assert len(calls) == 1 and isinstance(caught.value.__cause__, httpx.ConnectError)
    finally:
        await source.close()


@pytest.mark.parametrize("configured", [False, True])
def test_actual_vsb_permission_page_is_rejected_by_shared_html_validation(configured):
    html = (Path(__file__).parent / "fixtures/jlu_b4/permission-required.html").read_text(encoding="utf-8-sig")
    with pytest.raises((ValueError, SourceError), match="HTML_PERMISSION_REQUIRED"):
        if configured:
            parse_configured_html(html, "https://fixture.test/list", {"item_selector": "a"})
        else:
            parse_list_html(html, "https://fixture.test/list")


def test_notice_discussing_permission_error_is_not_a_permission_page():
    html = '<title>关于网站栏目权限的通知</title><div class="v_news_content">遇到“您没有访问当前栏目的权限”提示时，请联系管理员。</div>'
    from app.parsers import parse_detail_html
    item = NoticeCandidate(title="关于网站栏目权限的通知", url="https://fixture.test/info/1/1.htm")
    assert "联系管理员" in parse_detail_html(html, item.url, item).content


@pytest.mark.asyncio
async def test_audit_requests_keep_slash_and_query_separate_from_source_identity(monkeypatch, tmp_path):
    import importlib
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    audit = importlib.import_module("audit_jlu_sites")
    monkeypatch.setattr(audit, "EVIDENCE", tmp_path)
    async def allow(url, **kwargs):
        return url
    monkeypatch.setattr("app.sources.generic.validate_source_url", allow)
    fetch = audit.AuditFetch()
    await fetch.fetcher.client.aclose()
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, text="slash page" if request.url.path.endswith("/") else "other page")
    fetch.fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    plain = "https://fixture.test/column?b=2&a=1&utm_source=official"
    slash = "https://fixture.test/column/?b=2&a=1&utm_source=official"
    try:
        assert audit.norm(plain) == audit.norm(slash)
        assert (await fetch.get(plain))["html"] == "other page"
        assert (await fetch.get(slash + "#notice"))["html"] == "slash page"
        assert calls == [plain, slash]
        assert set(fetch.cache) == {plain, slash}
        assert (await fetch.get(slash))["html"] == "slash page" and len(calls) == 2
    finally:
        await fetch.close()
