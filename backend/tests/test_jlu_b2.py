from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
from app.api.routes import _serialize_notice
from app.config import Settings
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Favorite, Notice, NoticeSourceRelation, NoticeUpdate, Source, UserState
from app.parsers import parse_detail_html, parse_list_html
from app.schemas.notice import NoticeCandidate
from app.sources.base import StaticHTMLSource
from app.sources.generic import GenericPublicSource

FIXTURES = Path(__file__).parent / "fixtures/jlu_b2"
CONTROLS = {r["name"]: r for r in json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))}
URL = "https://fixture.test/info/1/1.htm"


def control(name):
    r = CONTROLS[name]
    listing = parse_list_html((FIXTURES / f"{name}.list.html").read_text(encoding="utf-8"), r["url"])
    return listing[0], parse_detail_html((FIXTURES / f"{name}.detail.html").read_text(encoding="utf-8"), r["detail_url"], listing[0])


def test_real_university_title_excludes_metadata_and_restores_truncation():
    listing, detail = control("university")
    assert listing.title.endswith("...")
    assert detail.title == "吉林大学附属中学2026年公开招聘教师（第三批次）笔试合格、进入面试环节人员名单公示"
    assert detail.publish_date == date(2026, 9, 6)


def test_real_student_calendar_ignores_summary_publicity_date():
    listing, detail = control("student")
    assert listing.publish_date == detail.publish_date == date(2026, 10, 13)


def test_real_food_calendar_title_excludes_date_and_summary():
    listing, detail = control("food")
    assert listing.title == detail.title == "公示食品科学与工程学院2023级本科生素质类加分分数及综合成绩排名的通知"
    assert listing.publish_date == detail.publish_date == date(2026, 9, 4)


def test_real_cse_image_is_retained_as_original_absolute_url_only():
    _, detail = control("image")
    assert detail.content == "https://cse.jlu.edu.cn/__local/1/41/25/AF491F76A40C0F5DF3EBAB45DE8_C9A85E37_63BD2B.jpg"
    assert detail.publish_date == date(2024, 7, 18)
    assert detail.attachments == [] and "<img" not in detail.content


@pytest.mark.parametrize("calendar,expected", [("31<span>2025-12</span>", date(2025, 12, 31)),
                                                   ("01<span>2026.01</span>", date(2026, 1, 1)),
                                                   ("29<span>2024-02</span>", date(2024, 2, 29)),
                                                   ("31<span>2026-02</span>", None)])
def test_split_calendar_cross_year_leap_day_and_invalid_date(calendar, expected):
    html = f'<ul><li><a href="/info/1/1.htm" title="测试通知"><p class="time">{calendar}</p><p>报名截止2026-03-01</p></a></li></ul>'
    assert parse_list_html(html, URL)[0].publish_date == expected


@pytest.mark.parametrize("body", ["报名截止：2026-10-20", "发布日期：2026-10-20", "无日期通知"])
def test_body_dates_do_not_establish_publication_date(body):
    html = '<div class="site-clock">2026-10-14</div><h2>通知公告</h2><div class="v_news_content">' + body + '</div>'
    detail = parse_detail_html(html, URL, NoticeCandidate(title="列表中的真实标题", url=URL))
    assert detail.publish_date is None and detail.title == "列表中的真实标题"


def test_summary_date_cannot_become_list_date_without_calendar():
    html = '<ul><li><a href="/info/1/1.htm" title="测试通知"><p class="info">公示2026-10-12起</p></a></li></ul>'
    assert parse_list_html(html, URL)[0].publish_date is None


@pytest.mark.parametrize("label", ["活动时间", "公示日期", "报名时间"])
def test_event_labels_in_metadata_do_not_establish_publication_date(label):
    html = f'<h1>测试通知</h1><div class="meta">{label}：2026-10-20</div><div class="v_news_content">有效正文</div>'
    assert parse_detail_html(html, URL, NoticeCandidate(title="测试通知", url=URL)).publish_date is None


def test_explicit_metadata_overrides_conflicting_list_date_without_body_inference():
    html = '<header><h1>学校首页</h1></header><h1>测试通知</h1><div class="meta">发布日期：2026-10-13</div><div class="v_news_content">报名截止2026-10-20</div>'
    detail = parse_detail_html(html, URL, NoticeCandidate(title="测试通知", url=URL, publish_date=date(2026, 10, 12)))
    assert detail.publish_date == date(2026, 10, 13) and detail.title == "测试通知"


def test_unscoped_site_heading_cannot_replace_list_title():
    html = '<h1>某学院官方网站</h1><h2>通知公告</h2><div class="v_news_content">有效通知正文</div>'
    detail = parse_detail_html(html, URL, NoticeCandidate(title="列表中的真实通知标题", url=URL))
    assert detail.title == "列表中的真实通知标题"


def test_pinned_old_date_is_not_replaced_by_clock_or_deadline():
    html = '<h1>测试通知</h1><span>2026-10-14</span><div class="v_news_content">报名截止2026-10-20</div>'
    detail = parse_detail_html(html, URL, NoticeCandidate(title="测试通知", url=URL, publish_date=date(2025, 12, 31)))
    assert detail.publish_date == date(2025, 12, 31)


@pytest.mark.parametrize("metadata", ['<p class="conttime"><span>日期：2026-09-21</span></p>',
                                     '<div class="title11"><p>发布时间：2026/09/21 13:33</p></div>'])
def test_observed_research_and_international_metadata_remain_supported(metadata):
    listing = '<ul><li><a href="/info/1/1.htm" title="测试通知"><h3>测试通知</h3><span>2026-09-21</span></a></li></ul>'
    item = parse_list_html(listing, URL)[0]
    assert item.publish_date == date(2026, 9, 21)
    detail = parse_detail_html('<h1>测试通知</h1>' + metadata + '<div class="v_news_content">活动时间2026-10-20</div>', URL,
                               item.model_copy(update={"publish_date": None}))
    assert detail.publish_date == date(2026, 9, 21)


@pytest.mark.parametrize("src", ["javascript:alert(1)", "data:image/png;base64,aaa", "http://127.0.0.1/a.jpg",
                                 "https://other.test/a.jpg", "/a.svg", "https://user:pass@fixture.test/a.jpg"])
def test_unverified_or_unsafe_image_references_remain_rejected(src):
    html = f'<h1>测试通知</h1><div class="v_news_content"><img src="{src}"></div>'
    with pytest.raises(ValueError, match="HTML_DETAIL_IMAGE_ONLY_UNSUPPORTED"):
        parse_detail_html(html, URL, NoticeCandidate(title="测试通知", url=URL))


def test_images_preserve_order_queries_and_short_body_without_html_execution():
    html = '<h1>测试通知</h1><div class="v_news_content"><p>今日停课。</p><img src="/a.jpg?id=1&amp;x=2" onerror="alert(1)"><img src="/a.jpg?id=1&amp;x=2"><img src="/b.png"><img src="/pixel.gif" width="1"></div>'
    detail = parse_detail_html(html, URL, NoticeCandidate(title="测试通知", url=URL))
    assert detail.content == "今日停课。 https://fixture.test/a.jpg?id=1&x=2 https://fixture.test/b.png"
    assert detail.attachments == []


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", [False, True])
async def test_static_and_generic_details_keep_images_without_fetching_them(configured, monkeypatch):
    html = '<h1>测试通知</h1><div class="v_news_content"><img src="/a.jpg"></div>'
    calls = []
    static = StaticHTMLSource({"code": "fixture", "name": "Fixture", "base_url": URL})
    async def get(url):
        calls.append(url)
        return html
    static._get = get
    async def allow(url, **kwargs):
        return url
    monkeypatch.setattr("app.sources.generic.validate_source_url", allow)
    generic = GenericPublicSource({"code": "fixture", "name": "Fixture", "base_url": URL,
                                   "parser_config": {"content_selector": ".v_news_content"} if configured else {}})
    async def fetch(url):
        return await get(url), "text/html", url
    generic.fetcher.get = fetch
    try:
        item = NoticeCandidate(title="测试通知", url=URL)
        assert (await static.fetch_detail(item)).content == (await generic.fetch_detail(item)).content == "https://fixture.test/a.jpg"
        assert calls == [URL, URL]
    finally:
        await static.close()
        await generic.close()


def test_date_and_title_correction_preserves_identity_and_user_state(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = Settings(_env_file=None, deployment_role="standalone", app_data_dir=str(tmp_path))
    monkeypatch.setattr(runner_module, "get_settings", lambda: settings)
    with Session(engine, expire_on_commit=False) as db:
        source = Source(code="fixture", name="Fixture", base_url=URL)
        db.add(source)
        db.commit()
        old = NoticeCandidate(title="较长的原列表标题...", url=URL, publish_date=date(2026, 10, 12), content="原正文")
        CrawlerManager._persist_candidate(db, source, old, True)
        notice = db.scalar(select(Notice))
        state = db.scalar(select(UserState))
        relation = db.scalar(select(NoticeSourceRelation))
        state.is_read = True
        state.is_favorite = True
        db.add(Favorite(notice_id=notice.id))
        db.commit()
        before = (notice.id, relation.id, state.id, state.is_read, state.is_favorite, state.updated_at)
        # A date-only fix must persist even when content_hash is unchanged.
        corrected = old.model_copy(update={"publish_date": date(2026, 10, 13)})
        assert CrawlerManager._persist_candidate(db, source, corrected, False) == "UPDATED"
        assert notice.publish_date == date(2026, 10, 13)
        corrected = corrected.model_copy(update={"title": "较长的原列表标题的完整版本", "content": "https://fixture.test/a.jpg"})
        assert CrawlerManager._persist_candidate(db, source, corrected, False) == "UPDATED"
        assert CrawlerManager._persist_candidate(db, source, corrected, False) == "UNCHANGED"
        db.expire_all()
        assert (notice.id, relation.id, state.id, state.is_read, state.is_favorite, state.updated_at) == before
        assert db.scalar(select(func.count(Notice.id))) == 1
        assert db.scalar(select(func.count(NoticeUpdate.id))) == 2
        assert db.scalar(select(Favorite.notice_id)) == notice.id
        dto = _serialize_notice(notice, detailed=True)
        assert dto["content"] == corrected.content and dto["publish_date"] == date(2026, 10, 13)
        assert CrawlerManager._persist_candidate(db, source, corrected.model_copy(update={"publish_date": None}), False) == "UNCHANGED"
        assert notice.publish_date == date(2026, 10, 13)
    engine.dispose()


def test_other_source_date_cannot_overwrite_canonical_notice(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(runner_module, "get_settings", lambda: Settings(_env_file=None, deployment_role="standalone", app_data_dir=str(tmp_path)))
    with Session(engine, expire_on_commit=False) as db:
        a, b = Source(code="a", name="A", base_url=URL), Source(code="b", name="B", base_url=URL)
        db.add_all([a, b]); db.commit()
        first = NoticeCandidate(title="同一条公开通知", url=URL, publish_date=date(2026, 10, 13), content="正文")
        CrawlerManager._persist_candidate(db, a, first, True)
        alias = first.model_copy(update={"url": "https://other.test/info/1/1.htm"})
        CrawlerManager._persist_candidate(db, b, alias, True, dedup_across_sources=True)
        CrawlerManager._persist_candidate(db, b, alias.model_copy(update={"publish_date": date(2026, 10, 12)}), False, dedup_across_sources=True)
        assert db.scalar(select(func.count(Notice.id))) == 1
        assert db.scalar(select(Notice)).publish_date == date(2026, 10, 13)
    engine.dispose()
