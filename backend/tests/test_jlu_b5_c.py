"""Bounded pagination and isolated incremental/state acceptance controls."""
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
import app.crawler.runner as runner
from app.crawler.runner import CrawlerManager, SourceRunResult
from app.database import Base
from app.models import Attachment, Favorite, Notice, NoticeSourceRelation, Source, UserState
from app.schemas.notice import AttachmentData, NoticeCandidate
import app.sources.base as base
import app.sources.generic as generic
from app.services.source_security import validate_local_source_url
from app.services.list_pagination import ListPagination
from app.parsers import parse_detail_html

ROOT = "https://fixture.test/notices.htm"


def listing(ids, href=None, attrs=""):
    rows = ''.join(f'<li><a href="/info/1/{i}.htm">第{i}项独立通知</a><span class="date">2026-10-14</span></li>' for i in ids)
    return f'<ul class="list">{rows}</ul>' + (f'<a class="next" href="{href}" {attrs}>下一页</a>' if href else '')


class Pages:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    async def get(self, url):
        self.calls.append(url)
        value = self.pages[url]
        html, final = value if isinstance(value, tuple) else (value, url)
        return html, "text/html", final

    async def validate_url(self, url):
        return await validate_local_source_url(url)

    async def close(self):
        pass


@pytest.fixture(params=["generic", "static"])
def adapter_factory(request, monkeypatch):
    settings = Settings(_env_file=None, max_items_per_section=2, source_max_pages=3)
    monkeypatch.setattr(generic, "get_settings", lambda: settings)
    monkeypatch.setattr(base, "get_settings", lambda: settings)

    async def make(pages, parser_config=None, url=ROOT):
        config = {"code": "fixture", "name": "fixture", "base_url": url,
                  "sections": [{"name": "通知", "url": url}], "parser_config": parser_config or {}}
        fetcher = Pages(pages)
        if request.param == "generic":
            adapter = generic.GenericPublicSource(config)
            await adapter.fetcher.close()
            adapter.fetcher = fetcher
        else:
            adapter = base.StaticHTMLSource(config)
            async def get_html(target):
                return (await fetcher.get(target))[0]
            async def get_page(target):
                html, _, final = await fetcher.get(target)
                return html, final
            adapter._get = get_html
            adapter._get_list_page = get_page
        return adapter, fetcher
    return make


@pytest.mark.asyncio
async def test_multiple_pages_are_retained_without_requesting_page_after_limit(adapter_factory):
    pages = {ROOT: listing([1, 2], "/notices/2.htm"), ROOT.replace(".htm", "/2.htm"): listing([3, 4], "/notices/1.htm")}
    adapter, fetcher = await adapter_factory(pages, {"next_page_selector": ".next", "pagination_limit": 2})
    try:
        items = await adapter.fetch_list()
        assert len(items) == 4
        assert fetcher.calls == list(pages)
    finally:
        await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["disabled", "cross_host", "cross_column", "javascript", "loop", "repeat"])
async def test_unsafe_disabled_or_repeating_pagination_stops_within_boundary(adapter_factory, case):
    target = {"disabled": "/notices/2.htm", "cross_host": "https://other.test/notices/2.htm",
              "cross_column": "/teaching.htm", "javascript": "javascript:nextPage()",
              "loop": "/notices/2.htm", "repeat": "/notices/2.htm"}[case]
    pages = {ROOT: listing([1, 2], target, 'aria-disabled="true"' if case == "disabled" else '')}
    if case in {"loop", "repeat"}:
        pages["https://fixture.test/notices/2.htm"] = listing([3, 4] if case == "loop" else [1, 2], ROOT if case == "loop" else "/notices/1.htm")
    adapter, fetcher = await adapter_factory(pages, {"next_page_selector": ".next", "pagination_limit": 3})
    try:
        items = await adapter.fetch_list()
        assert len(items) == (4 if case == "loop" else 2)
        assert fetcher.calls == list(pages)
        assert adapter.pagination_report[0]["stop_reason"] in {"DISABLED_NEXT_PAGE", "NEXT_PAGE_OUTSIDE_COLUMN", "INVALID_NEXT_LINK", "PAGE_CYCLE", "REPEATED_PAGE"}
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_no_pagination_configuration_preserves_first_page_only(adapter_factory):
    adapter, fetcher = await adapter_factory({ROOT: listing([1, 2, 3], "/notices/2.htm")})
    try:
        assert len(await adapter.fetch_list()) == 2 and fetcher.calls == [ROOT]
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_limit_one_with_selector_does_not_fetch_next_page(adapter_factory):
    adapter, fetcher = await adapter_factory({ROOT: listing([1, 2], "/notices/2.htm")}, {"next_page_selector": ".next", "pagination_limit": 1})
    try:
        assert len(await adapter.fetch_list()) == 2 and fetcher.calls == [ROOT]
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_same_path_query_must_keep_column_identity(adapter_factory):
    url = ROOT + "?cid=notices"
    adapter, fetcher = await adapter_factory({url: listing([1, 2], ROOT + "?cid=teaching&page=2")}, {"next_page_selector": ".next", "pagination_limit": 3}, url=url)
    try:
        assert len(await adapter.fetch_list()) == 2 and fetcher.calls == [url]
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_total_item_bound_stops_before_another_request(adapter_factory):
    adapter, fetcher = await adapter_factory({ROOT: listing(range(1, 12), "/notices/2.htm")}, {"next_page_selector": ".next", "pagination_limit": 3})
    try:
        assert len(await adapter.fetch_list()) == 6 and fetcher.calls == [ROOT]
        assert adapter.pagination_report[0]["truncated_items"] == 5
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_redirected_page_outside_column_is_not_accepted(adapter_factory):
    pages = {ROOT: listing([1, 2], "/notices/2.htm"), "https://fixture.test/notices/2.htm": (listing([3, 4]), "https://fixture.test/other.htm")}
    adapter, fetcher = await adapter_factory(pages, {"next_page_selector": ".next", "pagination_limit": 3})
    try:
        with pytest.raises((base.SourceError, ValueError), match="OUTSIDE_COLUMN"):
            await adapter.fetch_list()
        assert fetcher.calls == list(pages)
    finally:
        await adapter.close()


class MemoryAdapter:
    def __init__(self, items, details):
        self.items, self.details, self.calls = items, details, []

    async def fetch_list(self):
        return self.items

    async def fetch_detail(self, item):
        self.calls.append(item.url)
        value = self.details[item.url]
        if isinstance(value, Exception):
            raise value
        return value

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_failed_revision_recovers_without_advancing_failed_item_or_user_state(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    manager = CrawlerManager(tmp_path)
    settings = Settings(_env_file=None, deployment_role="standalone", app_data_dir=str(tmp_path))
    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    with Session(engine, expire_on_commit=False) as db:
        source = Source(code="fixture", name="fixture", base_url=ROOT)
        db.add(source)
        db.commit()
        original = NoticeCandidate(title="原始有效通知", url="https://fixture.test/info/1/1.htm", publish_date=date.today(), content="已有正文")
        manager._persist_candidate(db, source, original, True)
        notice = db.scalar(select(Notice))
        relation = db.scalar(select(NoticeSourceRelation))
        state = db.scalar(select(UserState))
        state.is_read = state.is_favorite = True
        db.add(Favorite(notice_id=notice.id))
        db.commit()
        ids = notice.id, relation.id
        before = relation.content_hash, notice.content, notice.version, state.updated_at
        changed = original.model_copy(update={"title": "恢复后的完整通知标题", "publish_date": date.today() - timedelta(days=1), "content": ""})
        another = NoticeCandidate(title="第二项独立通知", url="https://fixture.test/info/1/2.htm", publish_date=date.today())
        adapter = MemoryAdapter([changed, another], {changed.url: ValueError("DETAIL_FAILED"), another.url: another.model_copy(update={"content": "有效独立正文"})})
        monkeypatch.setattr(runner, "build_source", lambda _: adapter)
        config = {"code": "fixture", "name": "fixture", "base_url": ROOT}
        first = SourceRunResult(source="fixture")
        await manager._execute_source_attempt(db, source, config, False, first, "local")
        assert first.status == "partial_failure" and first.new_count == 1
        assert (relation.content_hash, notice.content, notice.version, state.updated_at) == before
        recovered = changed.model_copy(update={"content": "恢复正文与图片 https://fixture.test/image.png", "attachments": [AttachmentData(filename="资料.pdf", url="https://fixture.test/file.pdf", type="pdf")]})
        adapter.details[changed.url] = recovered
        second = SourceRunResult(source="fixture")
        await manager._execute_source_attempt(db, source, config, False, second, "local")
        assert second.status == "success" and second.updated_count == 1 and second.new_count == 0
        assert notice.id == ids[0] and relation.id == ids[1] and notice.status == "baseline"
        assert notice.title == recovered.title and notice.publish_date == recovered.publish_date
        assert notice.content == recovered.content and db.scalar(select(Attachment.filename)) == "资料.pdf"
        assert state.is_read and state.is_favorite and state.updated_at == before[3]
        assert db.scalar(select(Favorite.notice_id)) == notice.id
        third = SourceRunResult(source="fixture")
        await manager._execute_source_attempt(db, source, config, False, third, "local")
        assert third.new_count == third.updated_count == third.detail_fetched == 0 and third.detail_skipped == 2
        assert len(db.scalars(select(Notice)).all()) == 2
    engine.dispose()


def test_unchanged_list_metadata_matches_before_bounded_detail_recheck():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        source = Source(code="fixture", name="fixture", base_url=ROOT)
        db.add(source)
        db.commit()
        item = NoticeCandidate(title="已观察通知", url="https://fixture.test/info/1/1.htm", content="旧正文")
        CrawlerManager._persist_candidate(db, source, item, False)
        changed_body_only = item.model_copy(update={"content": ""})
        assert CrawlerManager._find_unchanged_list_item(db, source, changed_body_only) is not None
        # This is only the list metadata prefilter. The runner's bounded TTL
        # decision is covered by test_detail_refresh; no schema migration.
    engine.dispose()


@pytest.mark.parametrize("variant", ["valid", "post", "changed_script", "changed_cid", "external_action", "expression", "secret_input", "secret_hidden"])
def test_observed_get_form_pagination_requires_exact_public_structure(variant):
    html = (Path(__file__).parent / "fixtures/jlu_b5_c/employment-pagination.html").read_text(encoding="utf-8")
    if variant == "post":
        html = html.replace('method="get"', 'method="post"')
    elif variant == "changed_script":
        html = html.replace('$("#pageNo").val(n);', '$("#pageNo").val(n+1);')
    elif variant == "changed_cid":
        html = html.replace('value="jyzp_tzgg"', 'value="another"')
    elif variant == "external_action":
        html = html.replace('action="/portal', 'action="https://other.test/portal')
    elif variant == "expression":
        html = html.replace("page(2,12,'');", "page(1+1,12,'');")
    elif variant == "secret_input":
        html = html.replace('</form>', '<input name="password" type="password" value="secret"></form>')
    elif variant == "secret_hidden":
        html = html.replace('</form>', '<input name="token" type="hidden" value="secret"></form>')
    page_url = "https://fixture.test/portal/jyzp/article/list?cid=jyzp_tzgg"
    pager = ListPagination(page_url, {"next_page_selector": ".pagination li:last-child a", "pagination_limit": 3}, max_pages=3, items_per_section=30)
    item = NoticeCandidate(title="样本", url="https://fixture.test/info/1/1.htm")
    next_url = pager.consume(html, page_url, [item])
    if variant == "valid":
        assert parse_qs(urlsplit(next_url).query) == {"cid": ["jyzp_tzgg"], "pageNo": ["2"], "pageSize": ["12"]}
        assert pager.report["pages"][0]["next_link_kind"] == "OBSERVED_PUBLIC_GET_FORM"
    else:
        assert next_url is None


@pytest.mark.asyncio
async def test_query_pagination_accepts_same_column_and_retains_both_pages(adapter_factory):
    url = ROOT + "?cid=notices"
    second = ROOT + "?cid=notices&page=2"
    pages = {url: listing([1, 2], second), second: listing([2, 3])}
    adapter, fetcher = await adapter_factory(pages, {"next_page_selector": ".next", "pagination_limit": 3}, url=url)
    try:
        assert len(await adapter.fetch_list()) == 3 and fetcher.calls == list(pages)
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_old_pinned_item_does_not_stop_newer_items(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    manager = CrawlerManager(tmp_path)
    settings = Settings(_env_file=None, deployment_role="standalone", app_data_dir=str(tmp_path))
    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    old = NoticeCandidate(title="旧置顶通知", url="https://fixture.test/info/1/1.htm", publish_date=date.today() - timedelta(days=2000))
    new = NoticeCandidate(title="后续正常新通知", url="https://fixture.test/info/1/2.htm", publish_date=date.today(), content="新内容")
    adapter = MemoryAdapter([old, new], {new.url: new})
    monkeypatch.setattr(runner, "build_source", lambda _: adapter)
    with Session(engine) as db:
        source = Source(code="fixture", name="fixture", base_url=ROOT)
        db.add(source)
        db.commit()
        result = SourceRunResult(source="fixture")
        await manager._execute_source_attempt(db, source, {"code": "fixture", "name": "fixture", "base_url": ROOT}, False, result, "local")
        assert result.new_count == 1 and adapter.calls == [new.url]
        assert db.scalar(select(Notice.url)) == new.url
    engine.dispose()


@pytest.mark.parametrize("mode,expected", [("same_url", 1), ("tracking_alias", 1), ("same_title_other_source", 2), ("public_id", 1)])
def test_two_round_cross_source_identity_preserves_relations_and_states(mode, expected):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        sources = [Source(code=f"fixture-{i}", name=f"fixture-{i}", base_url=ROOT) for i in range(2)]
        db.add_all(sources)
        db.commit()
        first = NoticeCandidate(title="同名公开通知", url="https://fixture.test/info/1/1.htm", publish_date=date.today(), content="第一站正文")
        second = first.model_copy(update={"url": first.url if mode == "same_url" else first.url + "?utm_source=other" if mode == "tracking_alias" else "https://other.test/info/2/2.htm", "content": "第二站正文"})
        if mode == "public_id":
            first.public_id = second.public_id = "public-stable-identity"
        for iteration in range(2):
            for source, item in zip(sources, [first, second]):
                state = CrawlerManager._persist_candidate(db, source, item, False)
                if iteration:
                    assert state == "UNCHANGED"
            assert len(db.scalars(select(Notice)).all()) == expected
        relations = db.scalars(select(NoticeSourceRelation)).all()
        assert len(relations) == 2 and {r.source_id for r in relations} == {s.id for s in sources}
        assert len(db.scalars(select(UserState)).all()) == expected
        assert db.scalar(select(Notice).where(Notice.url == first.url)).public_id == first.public_id
    engine.dispose()


@pytest.mark.parametrize("suffixes", [("（一）", "（二）"), ("第一批", "第二批"), ("第17届", "第18届")])
def test_different_explicit_series_are_not_fuzzy_merged(suffixes, monkeypatch):
    # Mirrors the observed CSE summer-training notices 1369 and 1377.
    settings = Settings(_env_file=None, retention_days=3650, deployment_role="standalone")
    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        source = Source(code="cse", name="CSE", base_url="https://cse.jlu.edu.cn")
        db.add(source)
        db.commit()
        candidates = [NoticeCandidate(title="吉林大学网络安全学院暑期实训计划选拔通知" + suffix, url=f"https://cse.jlu.edu.cn/info/1006/{number}.htm", publish_date=date(2024, 7, day), content=f"独立方案{number}")
                      for suffix, number, day in [(suffixes[0], 1369, 1), (suffixes[1], 1377, 10)]]
        for candidate in candidates:
            assert CrawlerManager._persist_candidate(db, source, candidate, False) == "NEW"
        assert len(db.scalars(select(Notice)).all()) == 2
        for candidate in candidates:
            assert CrawlerManager._persist_candidate(db, source, candidate, False) == "UNCHANGED"
    engine.dispose()


@pytest.mark.parametrize("path", ["/__local/4/B0/98/document.pdf", "https://fixture.test/guide.pdf"])
def test_literal_vsb_pdf_body_is_retained_as_attachment_without_running_script(path):
    html = '<h1>参赛须知</h1><div class="v_news_content"><script>var vsb_pdf_image_data=[];showVsbpdfIframe("' + path + '","100%","800","0","border:1px solid #DDD",vsb_pdf_image_data);</script></div>'
    item = NoticeCandidate(title="参赛须知", url="https://fixture.test/info/1/1358.htm")
    parsed = parse_detail_html(html, item.url, item)
    assert len(parsed.attachments) == 1 and parsed.attachments[0].type == "pdf"
    assert parsed.attachments[0].url == "https://fixture.test" + path if path.startswith("/") else parsed.attachments[0].url == path
    assert "showVsbpdfIframe" not in parsed.content


@pytest.mark.parametrize("argument", ['"https://other.test/file.pdf"', '"javascript:alert(1).pdf"', 'buildPdfUrl()', '"https://user:secret@fixture.test/file.pdf"'])
def test_unsupported_or_external_pdf_script_does_not_make_an_empty_page_pass(argument):
    html = '<div class="v_news_content"><script>showVsbpdfIframe(' + argument + ',"100%","800");</script></div>'
    with pytest.raises(ValueError, match="HTML_DETAIL_EMPTY"):
        parse_detail_html(html, ROOT, NoticeCandidate(title="样本", url=ROOT))
