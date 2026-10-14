from __future__ import annotations

import json
from pathlib import Path
import ssl
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
from app.api.routes import _serialize_notice
from app.config import Settings
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Attachment, Favorite, Notice, Source, UserState
from app.parsers import parse_detail_html
from app.schemas.notice import NoticeCandidate
from app.services.attachment_validation import classify_attachment_prefix
from app.sources.base import SourceError, StaticHTMLSource
from app.sources.generic import GenericPublicSource
from app.sources.oa_public import OAAttachmentReference, OAPublicSource

FIXTURES = Path(__file__).parent / "fixtures/jlu_b3"
CONTROL = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
URL = "https://fixture.test/info/1/1.htm"


def parse(body, outside=""):
    return parse_detail_html('<form name="_newscontent_fromname"><h1>测试通知</h1><div class="v_news_content">' + body + '</div>' + outside + '</form>',
                             URL, NoticeCandidate(title="测试通知", url=URL))


def test_real_six_jpg_attachments_keep_names_order_and_query_identity():
    item = parse_detail_html((FIXTURES / "software-images.html").read_text(encoding="utf-8"), CONTROL["url"],
                             NoticeCandidate(title="离线附件通知", url=CONTROL["url"]))
    assert [(a.filename, a.url, a.type) for a in item.attachments] == [(f["filename"], "https://csw.jlu.edu.cn" + f["href"], "jpg") for f in CONTROL["files"]]


@pytest.mark.parametrize("extension", ["jpg", "png", "rar", "7z", "ppt", "pptx", "csv", "txt"])
def test_extra_types_require_explicit_attachment_context(extension):
    assert parse(f'正文链接<a href="/file.{extension}">file.{extension}</a>').attachments == []
    item = parse('有效正文', f'<ul><li>附件【<a href="/file.{extension}">file.{extension}</a>】</li></ul>')
    assert item.attachments[0].type == extension


def test_navigation_footer_logo_and_inline_images_are_not_attachments():
    html = '<nav><a href="/guide.pdf">学校介绍.pdf</a></nav><form name="_newscontent_fromname"><h1>测试通知</h1><div class="v_news_content">正文<img src="/notice.jpg"><a href="/zoom.jpg">放大图片</a><a href="/form.pdf">申请表.pdf</a></div></form><footer><div class="attachments"><a href="/logo.png">logo.png</a><a href="/manual.pdf">手册.pdf</a></div></footer>'
    item = parse_detail_html(html, URL, NoticeCandidate(title="测试通知", url=URL))
    assert [(a.filename, a.type) for a in item.attachments] == [("申请表.pdf", "pdf")]
    assert "https://fixture.test/notice.jpg" in item.content


def test_attachment_only_sibling_container_and_duplicate_urls():
    item = parse('', '<div class="attachments"><a href="/form.PDF?id=2&amp;owner=3">申请表.PDF</a><a href="/form.PDF?id=2&amp;owner=3">重复.PDF</a></div>')
    assert item.content == "" and len(item.attachments) == 1
    assert item.attachments[0].url == "https://fixture.test/form.PDF?id=2&owner=3"
    assert item.attachments[0].type == "pdf"


def test_legacy_opaque_download_query_and_empty_anchor_filename():
    files = parse('<a href="/get.jsp?file=report.pdf">下载</a><a href="/files/%E7%94%B3%E8%AF%B7%E8%A1%A8.xlsx"></a>').attachments
    assert [f.type for f in files] == ["pdf", "xlsx"]
    assert files[1].filename == "申请表.xlsx"


@pytest.mark.parametrize("href", ["javascript:alert(1).pdf", "data:application/pdf;base64,AA", "https://user:pass@fixture.test/a.pdf", "&lt;bad&gt;.pdf"])
def test_unsafe_attachment_href_rejected_without_network(href):
    assert parse(f'正文<a href="{href}">file.pdf</a>').attachments == []


@pytest.mark.asyncio
async def test_static_attachment_literal_private_address_is_removed():
    source = StaticHTMLSource({"code": "fixture", "name": "Fixture", "base_url": URL})
    async def get(url):
        return '<h1>测试通知</h1><div class="v_news_content">正文<a href="http://127.0.0.1/a.pdf">file.pdf</a><a href="/good.pdf">good.pdf</a></div>'
    source._get = get
    try:
        item = await source.fetch_detail(NoticeCandidate(title="测试通知", url=URL))
        assert [a.url for a in item.attachments] == ["https://fixture.test/good.pdf"]
    finally:
        await source.close()


@pytest.mark.asyncio
async def test_generic_dedup_and_private_source_policy_are_preserved(monkeypatch):
    async def policy(url, **kwargs):
        from app.services.source_security import validate_local_source_url
        return await validate_local_source_url(url, allow_private_network=kwargs["allow_private_network"])
    monkeypatch.setattr("app.sources.generic.validate_source_url", policy)
    for private in (False, True):
        source = GenericPublicSource({"code": "fixture", "name": "Fixture", "base_url": URL, "allow_private_network": private})
        async def get(url):
            return '<h1>测试通知</h1><div class="v_news_content">正文<a href="http://127.0.0.1/a.pdf">file.pdf</a><a href="/good.pdf">good.pdf</a><a href="/good.pdf">duplicate.pdf</a></div>', "text/html", url
        source.fetcher.get = get
        try:
            item = await source.fetch_detail(NoticeCandidate(title="测试通知", url=URL))
            assert len(item.attachments) == (2 if private else 1)
        finally:
            await source.close()


@pytest.mark.parametrize("prefix,kind", [(b"%PDF-1.7\n", "pdf"), (b"\xff\xd8\xff\xe0", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"), (b"GIF89a", "gif"), (b"RIFF0000WEBP", "webp"),
    (b"PK\x03\x04", "docx"), (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "xls"),
    (b"Rar!\x1a\x07", "rar"), (b"7z\xbc\xaf\x27\x1c", "7z")])
def test_recognized_prefix_is_only_prefix_evidence(prefix, kind):
    result = classify_attachment_prefix(206, {"content-type": "application/octet-stream"}, prefix, kind)
    assert result["category"] == "FILE_PREFIX_VERIFIED" and result["file_prefix_verified"]
    assert result["complete_download_verified"] is False


@pytest.mark.parametrize("status,mime,prefix,category", [
    (200, "text/html", b"<html>Download instructions</html>", "DOWNLOAD_HTML_PAGE"),
    (206, "application/octet-stream", '<script>请输入验证码</script>'.encode(), "CAPTCHA_REQUIRED"),
    (200, "text/html", b'<form><input type="password"></form>', "AUTH_REQUIRED"),
    (200, "text/html", '<html>仅限校内 IP</html>'.encode(), "ACCESS_RESTRICTED_PAGE"),
    (200, "application/octet-stream", b"", "EMPTY_RESPONSE"),
    (200, "application/octet-stream", b"random error response", "UNKNOWN_PREFIX"),
    (200, "text/csv", b"name,score\nA,1", "TEXT_FILE_UNVERIFIED"),
    (403, "text/html", b"Forbidden", "ACCESS_DENIED"), (429, "text/html", b"slow down", "RATE_LIMITED"),
    (404, "text/html", b"not found", "NOT_FOUND"), (302, "text/html", b"", "REDIRECT_NOT_FOLLOWED"),
])
def test_status_nonempty_and_disposition_alone_never_prove_file(status, mime, prefix, category):
    result = classify_attachment_prefix(status, {"content-type": mime, "content-disposition": 'attachment;filename="notice.pdf"'}, prefix)
    assert result["category"] == category and not result["file_prefix_verified"]


def test_header_and_type_conflicts_remain_unverified():
    assert classify_attachment_prefix(200, {"content-type": "text/html"}, b"%PDF-1.7")["category"] == "HEADER_BODY_MISMATCH"
    assert classify_attachment_prefix(200, {}, b"%PDF-1.7", "jpg")["category"] == "FILE_TYPE_MISMATCH"
    assert classify_attachment_prefix(200, {"Content-Type": "text/html"}, b"%PDF-1.7")["category"] == "HEADER_BODY_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["large_file", "login_redirect", "forbidden", "unsafe"])
async def test_prefix_probe_is_bounded_cached_and_does_not_follow_authentication(mode, tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("JLU_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JLU_APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("JLU_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("JLU_STARTUP_SYNC_ENABLED", "false")
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    module = importlib.import_module("probe_jlu_b3")
    monkeypatch.setattr(module.audit, "EVIDENCE", tmp_path)
    calls = []
    chunks = []
    class LargeFile(httpx.AsyncByteStream):
        async def __aiter__(self):
            for index in range(100):
                chunks.append(index)
                yield (b"%PDF-1.7" + b"x" * 1016) if index == 0 else b"x" * 1024
    def respond(request):
        calls.append(request)
        if mode == "login_redirect":
            return httpx.Response(302, headers={"location": "https://fixture.test/login"})
        if mode == "forbidden":
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(200, headers={"content-type": "application/pdf"}, stream=LargeFile())
    fetch = module.PrefixAudit()
    await fetch.fetcher.client.aclose()
    fetch.fetcher.client = httpx.AsyncClient(transport=httpx.MockTransport(respond),
                                            event_hooks={"request": [fetch.before], "response": [fetch.after]})
    async def validate(url):
        if mode == "unsafe":
            from app.services.source_security import UnsafeSourceUrl
            raise UnsafeSourceUrl("Rejected by URL policy")
        return url
    async def robots(url):
        return None
    fetch.fetcher.validate_url = validate
    fetch.check_robots = robots
    try:
        result = await fetch.probe("https://fixture.test/file.pdf", "pdf")
        assert await fetch.probe("https://fixture.test/file.pdf", "pdf") == result
        assert result["category"] == {"large_file": "FILE_PREFIX_VERIFIED", "login_redirect": "AUTH_REQUIRED",
                                      "forbidden": "ACCESS_DENIED", "unsafe": "URL_SECURITY_REJECTED"}[mode]
        assert len(calls) == (0 if mode == "unsafe" else 1)
        if mode == "large_file":
            assert result["read_bytes"] == 4096 and len(chunks) == 4
            assert result["complete_download_verified"] is False
            assert calls[0].headers["range"] == "bytes=0-4095"
    finally:
        await fetch.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "html", "403", "429", "503", "tls"])
async def test_oa_real_encoder_request_and_bounded_error_handling(mode):
    calls = []
    reference = OAAttachmentReference("20260101.pdf", "附件 申请表.pdf", "12345")
    def respond(request):
        calls.append(request)
        if mode == "tls":
            error = httpx.ConnectError("", request=request)
            error.__cause__ = ssl.SSLCertVerificationError(1, "CERTIFICATE_VERIFY_FAILED")
            raise error
        if mode.isdigit():
            return httpx.Response(int(mode), text="rejected")
        return httpx.Response(200, text="AA+/=token" if mode == "success" else "<html>verification</html>")
    source = OAPublicSource({"code": "oa", "name": "OA", "base_url": "https://oa.fixture.test"})
    await source.client.aclose()
    source.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    source.retries = 1
    source.backoff = 0
    try:
        if mode == "success":
            url = await source._attachment_url(reference, "https://oa.fixture.test/detail?id=12345")
            assert parse_qs(httpx.URL(url).query.decode())["res"] == ["AA+/=token"]
            assert calls[0].method == "POST" and calls[0].url.path == "/defaultroot/rd/download/BASEEncoderAjax.jsp"
            assert parse_qs(calls[0].content.decode())["res"] == [reference.encoder_value]
            assert calls[0].headers["referer"] == "https://oa.fixture.test/detail?id=12345"
        else:
            with pytest.raises(SourceError):
                await source._attachment_url(reference, "https://oa.fixture.test/detail?id=12345")
        assert len(calls) == (2 if mode == "503" else 1)
    finally:
        await source.close()


def test_six_attachments_persist_once_without_losing_user_state(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(runner_module, "get_settings", lambda: Settings(_env_file=None, deployment_role="standalone", app_data_dir=str(tmp_path)))
    item = parse_detail_html((FIXTURES / "software-images.html").read_text(encoding="utf-8"), CONTROL["url"], NoticeCandidate(title="离线附件通知", url=CONTROL["url"]))
    with Session(engine, expire_on_commit=False) as db:
        source = Source(code="fixture", name="Fixture", base_url=CONTROL["url"])
        db.add(source); db.commit()
        CrawlerManager._persist_candidate(db, source, item.model_copy(update={"attachments": []}), True)
        notice = db.scalar(select(Notice)); state = db.scalar(select(UserState))
        state.is_read = True; state.is_favorite = True; db.add(Favorite(notice_id=notice.id)); db.commit()
        before = (notice.id, state.is_read, state.is_favorite, state.updated_at)
        for _ in range(2):
            CrawlerManager._persist_candidate(db, source, item, False)
        db.expire_all()
        assert db.scalar(select(func.count(Notice.id))) == 1
        assert db.scalar(select(func.count(Attachment.id))) == 6
        assert (notice.id, state.is_read, state.is_favorite, state.updated_at) == before
        assert db.scalar(select(Favorite.notice_id)) == notice.id
        dto = _serialize_notice(notice, detailed=True)
        assert len(dto["attachments"]) == 6
        assert all(set(a) == {"filename", "url", "type"} for a in dto["attachments"])
    engine.dispose()
