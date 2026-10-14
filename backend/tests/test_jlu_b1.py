from __future__ import annotations

import json
import logging
from pathlib import Path
import ssl

from fastapi import HTTPException
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
import app.api.source_management as source_api
import app.api.cloud_admin as cloud_api
from app.config import Settings
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.logging_config import JsonFormatter
from app.models import Favorite, Notice, NoticeSourceRelation, Source, UserState
from app.parsers import parse_detail_html, parse_list_html
from app.parsers.html import is_empty_notice_list
from app.schemas.notice import NoticeCandidate
from app.sources.base import SourceError, StaticHTMLSource
from app.sources.generic import GenericPublicSource, SafeFetcher, parse_configured_html

FIXTURES = Path(__file__).parent / "fixtures/jlu_b1"
CONTROLS = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
BAD_DETAIL = '<html><h1>测试通知</h1><div class="content"><nav><a href="index.htm">学校首页</a><a href="xygk.htm">学院概况</a></nav></div></html>'
GOOD_LIST = '<div class="list"><ul><li><a href="/info/1/1.htm">测试通知</a><span>2026-10-13</span></li></ul></div>'


@pytest.fixture(autouse=True)
def local_fixture_network(monkeypatch):
    async def allow_fixture(url, **kwargs):
        return url
    monkeypatch.setattr("app.sources.generic.validate_source_url", allow_fixture)
    monkeypatch.setattr(logging.getLogger("app.sources.generic"), "disabled", False)


@pytest.mark.parametrize("control", [c for c in CONTROLS if c["name"] != "empty-column"], ids=lambda c: c["name"])
def test_existing_source_structural_controls(control):
    listing = (FIXTURES / (control["name"] + ".list.html")).read_text(encoding="utf-8")
    detail = (FIXTURES / (control["name"] + ".detail.html")).read_text(encoding="utf-8")
    items = parse_list_html(listing, control["url"])
    assert len(items) == 1
    assert items[0].url == control["detail_url"]
    parsed = parse_detail_html(detail, items[0].url, items[0])
    assert parsed.title == "离线样本通知"
    assert "离线正文" in parsed.content


def test_real_empty_column_does_not_promote_navigation():
    html = (FIXTURES / "empty-column.html").read_text(encoding="utf-8")
    assert is_empty_notice_list(html)
    assert parse_list_html(html, "https://auto.jlu.edu.cn/zsxx.htm") == []


def test_navigation_article_paths_and_malformed_links_are_excluded():
    html = '<div class="nav"><ul><li><a href="/info/1/2.htm">学校简介</a></li></ul></div>' + GOOD_LIST
    html += '<ul><li><a href="&lt;span&gt;转换链接错误&lt;/span&gt;">错误通知</a></li></ul>'
    assert [n.url for n in parse_list_html(html, "https://fixture.test/list.htm")] == ["https://fixture.test/info/1/1.htm"]


def test_non_vsb_dated_row_remains_supported():
    html = '<ul><li><a href="notice.htm">临时停课通知</a> 2026-10-13</li><li><a href="xygk.htm">学院概况</a></li></ul>'
    assert [n.url for n in parse_list_html(html, "https://fixture.test/list")] == ["https://fixture.test/notice.htm"]


@pytest.mark.parametrize("html", [
    '<html><h1>测试通知</h1><body>学校首页 学院概况 友情链接 版权所有</body></html>',
    BAD_DETAIL,
    '<html><title>用户登录</title><div class="content"><form><input type="password"></form></div></html>',
    '<html><title>404 Not Found</title><div class="content">The document was not found.</div></html>',
    '<html><title>安全验证</title><div class="content">请完成验证后访问</div></html>',
    '<html><h1>测试通知</h1><div class="v_news_content"><script>fake notice</script></div></html>',
])
def test_interstitial_navigation_and_empty_details_rejected(html):
    with pytest.raises(ValueError, match="HTML_"):
        parse_detail_html(html, "https://fixture.test/info/1/1.htm", NoticeCandidate(title="测试通知", url="https://fixture.test/info/1/1.htm"))


@pytest.mark.parametrize("body", ["<p>今日停课。</p>", '<a href="/files/form.pdf"></a>'])
def test_short_and_attachment_only_notice_still_parse(body):
    parsed = parse_detail_html('<h1>测试通知</h1><div class="v_news_content">' + body + '</div>',
                               "https://fixture.test/info/1/1.htm", NoticeCandidate(title="测试通知", url="https://fixture.test/info/1/1.htm"))
    assert parsed.content == "今日停课。" or parsed.attachments[0].filename == "form.pdf"


def test_unsupported_image_notice_is_reported_as_unsupported_not_empty():
    html = '<h1>图片通知</h1><div class="v_news_content"><img src="/notice.svg"></div>'
    with pytest.raises(ValueError, match="HTML_DETAIL_IMAGE_ONLY_UNSUPPORTED"):
        parse_detail_html(html, "https://fixture.test/info/1/1.htm", NoticeCandidate(title="图片通知", url="https://fixture.test/info/1/1.htm"))


@pytest.mark.asyncio
async def test_static_empty_list_and_unknown_template_are_different():
    adapter = StaticHTMLSource({"code": "fixture", "name": "fixture", "base_url": "https://fixture.test", "sections": [{"url": "https://fixture.test/list"}]})
    html = (FIXTURES / "empty-column.html").read_text(encoding="utf-8")
    async def get(url):
        return html
    adapter._get = get
    try:
        assert await adapter.fetch_list() == []
        html = '<html><ul><li><a href="index.htm">首页</a></li></ul></html>'
        with pytest.raises(SourceError, match="HTML_LIST_UNSUPPORTED"):
            await adapter.fetch_list()
    finally:
        await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", [False, True])
async def test_preview_rejects_bad_detail_without_issuing_token(configured, monkeypatch):
    original = GenericPublicSource
    closed = []
    def adapter(config):
        source = original(config)
        async def get(url):
            return (GOOD_LIST if url.endswith("list.htm") else BAD_DETAIL), "text/html", url
        source.fetcher.get = get
        original_close = source.close
        async def close():
            await original_close()
            closed.append(True)
        source.close = close
        return source
    monkeypatch.setattr(source_api, "GenericPublicSource", adapter)
    count = len(source_api._preview_tokens)
    draft = source_api.SourceDraft(name="Fixture", list_url="https://fixture.test/list.htm",
                                  parser_config=source_api.ParserConfiguration(content_selector=".content" if configured else None))
    with pytest.raises(HTTPException) as error:
        await source_api.preview_source(draft)
    assert error.value.status_code == 422 and "HTML_DETAIL_NAVIGATION" in error.value.detail
    assert len(source_api._preview_tokens) == count and closed == [True]


@pytest.mark.asyncio
async def test_generic_empty_preview_reports_empty_and_no_token(monkeypatch):
    html = (FIXTURES / "empty-column.html").read_text(encoding="utf-8")
    original = GenericPublicSource
    def adapter(config):
        source = original(config)
        async def get(url):
            return html, "text/html", url
        source.fetcher.get = get
        return source
    monkeypatch.setattr(source_api, "GenericPublicSource", adapter)
    count = len(source_api._preview_tokens)
    with pytest.raises(HTTPException, match="HTML_LIST_EMPTY"):
        await source_api.preview_source(source_api.SourceDraft(name="Fixture", list_url="https://fixture.test/list.htm"))
    assert len(source_api._preview_tokens) == count


@pytest.mark.asyncio
async def test_cloud_preview_uses_same_detail_gate(monkeypatch):
    async def allow(url, **kwargs):
        return url
    monkeypatch.setattr(cloud_api, "validate_cloud_source_url", allow)
    original = GenericPublicSource
    def adapter(config):
        assert config["validation_scope"] == "cloud" and not config["allow_private_network"]
        source = original(config)
        async def get(url):
            return (GOOD_LIST if url.endswith("list.htm") else BAD_DETAIL), "text/html", url
        source.fetcher.get = get
        return source
    monkeypatch.setattr(cloud_api, "GenericPublicSource", adapter)
    with pytest.raises(HTTPException, match="HTML_DETAIL_NAVIGATION"):
        await cloud_api._cloud_preview(cloud_api.CloudSourceDraft(name="Fixture", list_url="https://fixture.test/list.htm"))


@pytest.mark.asyncio
async def test_configured_attachment_outside_empty_body_remains_supported():
    source = GenericPublicSource({"code": "fixture", "name": "Fixture", "base_url": "https://fixture.test/list.htm",
                                  "parser_config": {"content_selector": ".article-content", "attachment_selector": ".attachments a"}})
    async def get(url):
        return '<h1>附件通知</h1><div class="article-content"></div><div class="attachments"><a href="/form.pdf">申请表.pdf</a></div>', "text/html", url
    source.fetcher.get = get
    try:
        parsed = await source.fetch_detail(NoticeCandidate(title="附件通知", url="https://fixture.test/info/1/1.htm"))
        assert parsed.content == "" and parsed.attachments[0].url == "https://fixture.test/form.pdf"
    finally:
        await source.close()


def test_explicit_selector_cannot_promote_navigation():
    with pytest.raises(SourceError, match="did not find"):
        parse_configured_html('<nav><ul><li><a href="index.htm">首页</a></li></ul></nav>',
                              "https://fixture.test/list", {"item_selector": "li"})


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["eof", "timeout", "http", "certificate"])
async def test_safe_fetcher_preserves_causes_and_sanitized_diagnostics(kind, caplog):
    calls = []
    def respond(request):
        calls.append(request)
        if kind == "http":
            return httpx.Response(503, text="unavailable")
        if kind == "timeout":
            raise httpx.ReadTimeout("", request=request)
        error = httpx.ConnectError("", request=request)
        error.__cause__ = ssl.SSLCertVerificationError(1, "CERTIFICATE_VERIFY_FAILED") if kind == "certificate" else ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING")
        raise error
    fetcher = SafeFetcher(transport=httpx.MockTransport(respond), source_code="fixture")
    fetcher.retries = 1
    fetcher.backoff = 0
    caplog.set_level(logging.INFO)
    try:
        with pytest.raises(SourceError) as error:
            await fetcher.get("https://fixture.test/list?token=secret#private")
        assert error.value.__cause__ is not None
        expected = {"eof": "SSLEOFError", "timeout": "ReadTimeout", "http": "503", "certificate": "TLS_CERTIFICATE_VERIFY_FAILED"}[kind]
        assert expected in str(error.value)
        assert len(calls) == (1 if kind == "certificate" else 2)
        records = [json.loads(JsonFormatter().format(r)) for r in caplog.records if getattr(r, "event", "") == "source_http_request_failed"]
        assert len(records) == len(calls)
        assert records[0]["url"] == "https://fixture.test/list"
        assert "secret" not in json.dumps(records) and "#private" not in json.dumps(records)
        assert records[0]["http_status"] == 503 if kind == "http" else "http_status" not in records[0]
    finally:
        await fetcher.close()


@pytest.mark.asyncio
async def test_bad_detail_does_not_overwrite_state_and_good_notice_continues(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    adapter = StaticHTMLSource({"code": "fixture", "name": "fixture", "base_url": "https://fixture.test", "sections": [{"url": "https://fixture.test/list"}]})
    bad = True
    async def get(url):
        if url.endswith("list"):
            return GOOD_LIST.replace('</ul>', '<li><a href="/info/1/2.htm">另一条通知</a></li></ul>')
        if url.endswith("1.htm") and bad:
            return BAD_DETAIL
        return '<h1>测试通知</h1><div class="v_news_content">保留的有效正文。</div>'
    adapter._get = get
    settings = Settings(_env_file=None, deployment_role="standalone", app_data_dir=str(tmp_path))
    monkeypatch.setattr(runner_module, "get_settings", lambda: settings)
    monkeypatch.setattr(runner_module, "build_source", lambda _: adapter)
    with Session(engine, expire_on_commit=False) as db:
        source = Source(code="fixture", name="fixture", base_url="https://fixture.test")
        db.add(source)
        db.commit()
        monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
        manager = CrawlerManager(tmp_path)
        good = NoticeCandidate(title="旧标题", url="https://fixture.test/info/1/1.htm", content="原有正文")
        manager._persist_candidate(db, source, good, True)
        db.commit()
        existing = db.scalar(select(Notice).where(Notice.url == good.url))
        state = db.scalar(select(UserState).where(UserState.notice_id == existing.id))
        state.is_read = True
        state.is_favorite = True
        db.add(Favorite(notice_id=existing.id))
        db.commit()
        notice_id = existing.id
        relation_id = db.scalar(select(NoticeSourceRelation.id).where(NoticeSourceRelation.notice_id == notice_id))
        before_state = (state.is_read, state.is_favorite, state.updated_at)
        result = await manager._run_source({"code": "fixture", "name": "fixture", "base_url": "https://fixture.test", "parser": "generic_html"}, False)
        assert result.status == "partial_failure" and any("HTML_DETAIL_NAVIGATION" in e for e in result.errors)
        db.expire_all()
        assert db.get(Notice, notice_id).content == "原有正文"
        state = db.scalar(select(UserState).where(UserState.notice_id == notice_id))
        assert (state.is_read, state.is_favorite, state.updated_at) == before_state
        assert db.scalar(select(Favorite.notice_id)) == notice_id
        assert db.scalar(select(NoticeSourceRelation.id).where(NoticeSourceRelation.notice_id == notice_id)) == relation_id
        assert db.scalar(select(Notice).where(Notice.url.endswith("2.htm"))) is not None
    engine.dispose()
