"""Real B6 empty-page controls and CMS heading/date boundaries."""
from datetime import date
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.parsers import parse_detail_html, parse_list_html
from app.parsers.html import is_empty_notice_list
from app.schemas.notice import NoticeCandidate
from app.sources.generic import GenericPublicSource, parse_configured_html

FIXTURES = Path(__file__).parent / "fixtures/jlu_b6"
CONTROLS = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def preserve_environment_when_importing_audit_helpers():
    # Audit entry points intentionally set isolated runtime defaults. Importing
    # one for a unit check must not change later tests' application defaults.
    with patch.dict(os.environ, os.environ.copy(), clear=True):
        yield


@pytest.mark.parametrize("control", [c for c in CONTROLS if c["kind"] in {"vsb-empty", "hospital-empty"}], ids=lambda c: c["file"])
def test_real_server_rendered_empty_columns_are_recognized_without_navigation(control):
    html = (FIXTURES / control["file"]).read_text(encoding="utf-8")
    html += '<nav><ul><li><a href="/info/1/1.htm">其他栏目导航</a></li></ul></nav>'
    assert is_empty_notice_list(html)
    assert parse_list_html(html, control["url"]) == []


def test_zero_page_goto_and_disabled_pager_do_not_hide_real_articles():
    control = next(c for c in CONTROLS if c["kind"] == "vsb-empty")
    html = (FIXTURES / control["file"]).read_text(encoding="utf-8")
    html += '<ul><li><a href="/info/1/2.htm">正常通知</a><span>2026-10-15</span></li></ul>'
    assert not is_empty_notice_list(html)
    assert len(parse_list_html(html, control["url"])) == 1


def test_generic_empty_markup_and_footer_pagers_are_not_zero_column_proof():
    assert not is_empty_notice_list('<ul></ul><div>没有查询结果</div>')
    assert not is_empty_notice_list('<footer><div class="pb_sys_common"><span class="p_no_d">1</span><span class="p_next_d">下页</span><span class="p_last_d">尾页</span></div></footer>')


@pytest.mark.parametrize("path", ["/wujia_detail_g7yU_62/177728.html", "/tongzhiy/detail_g7yU_91/227840.html"])
def test_discovery_does_not_treat_hospital_articles_as_columns(path):
    from scripts.audit_jlu_sites import column_links
    html = f'<a href="{path}">关于奖学金评审工作的通知</a><a href="/wujiaquery_g7yU_62.html">通知公告</a>'
    assert column_links(html, "https://www.zrlyyy.com/") == {"https://www.zrlyyy.com/wujiaquery_g7yU_62.html": "通知公告"}


def test_hospital_selectors_keep_truncated_title_separate_from_list_date():
    html = (FIXTURES / "hospital.list.html").read_text(encoding="utf-8")
    config = {"item_selector": '.list > .li:has(> a[href^="/wujia_detail_g7yU_59/"])',
              "title_selector": "a > .p", "url_selector": 'a[href^="/wujia_detail_g7yU_59/"]', "time_selector": "a > .y"}
    items = parse_configured_html(html, "https://www.zrlyyy.com/wujiaquery_g7yU_59.html", config)
    assert len(items) == 6 and items[0].publish_date == date(2026, 9, 29)
    assert "2026.09.29" not in items[0].title


@pytest.mark.parametrize("metadata", [
    '<div class="txt_title"><h5>学院研究生奖学金评审通知</h5><span><i>时间：2026-10-14</i></span></div>',
    '<div class="cont_con14_4_tit"><h3>学院研究生奖学金评审通知</h3><p>发布时间：2026-10-14</p></div>',
    '<div class="tittle">学院研究生奖学金评审通知</div><div class="pe_data">发布日期：2026-10-14</div>',
])
def test_observed_vsb_headings_restore_titles_and_take_only_article_metadata(metadata):
    html = '<form name="_newscontent_fromname">' + metadata + '<div class="v_news_content">活动日期：2027-01-01，请关注安排。</div></form>'
    parsed = parse_detail_html(html, "https://fixture.test/info/1/2.htm", NoticeCandidate(title="学院研究生...", url="https://fixture.test/info/1/2.htm"))
    assert parsed.title == "学院研究生奖学金评审通知" and parsed.publish_date == date(2026, 10, 14)


def test_explicit_video_attachment_keeps_download_identity_without_capturing_body_images():
    html = '<h1>火炬设计发布</h1><form name="_newscontent_fromname"><div class="v_news_content">正文<img src="/logo.png"></div><ul><li>附件【<a href="/system/_content/download.jsp?urltype=news.DownloadAttachUrl&amp;owner=1774901720&amp;wbfileid=18206109">设计发布.mp4</a>】</li></ul></form>'
    parsed = parse_detail_html(html, "https://fixture.test/info/1/2.htm", NoticeCandidate(title="火炬设计发布", url="https://fixture.test/info/1/2.htm"))
    assert len(parsed.attachments) == 1 and parsed.attachments[0].type == "mp4"
    assert parsed.attachments[0].url.endswith("owner=1774901720&wbfileid=18206109")


@pytest.mark.parametrize("frame", ["form name='_newscontent_fromname'", "div class='neirong'"])
def test_unknown_vsb_header_requires_scope_and_corroboration(frame):
    closing = frame.split()[0]
    html = f'<title>完整的学院通知-学院</title><{frame}><h5>完整的学院通知</h5><div class="new-layout"><span>发布日期：2026-10-14</span></div><div class="v_news_content"><h3>正文小标题</h3>活动日期：2027-01-01</div></{closing}>'
    parsed = parse_detail_html(html, "https://fixture.test/info/1/2.htm", NoticeCandidate(title="完整的...", url="https://fixture.test/info/1/2.htm"))
    assert parsed.title == "完整的学院通知" and parsed.publish_date == date(2026, 10, 14)


@pytest.mark.parametrize("metadata", [
    '<div>更新时间：2026-10-14</div>',
    '<div>发布日期：2026-10-14</div><div>发布日期：2026-10-15</div>',
])
def test_unknown_header_update_or_conflict_does_not_invent_publication(metadata):
    html = '<form name="_newscontent_fromname">' + metadata + '<div class="v_news_content">发布日期：2027-01-01是活动说明</div></form>'
    parsed = parse_detail_html(html, "https://fixture.test/info/1/2.htm", NoticeCandidate(title="学院通知", url="https://fixture.test/info/1/2.htm"))
    assert parsed.publish_date is None


def test_dated_vsb_article_row_does_not_turn_its_section_tag_into_a_notice():
    html = '<ul class="list"><li><a href="/djgz.htm">党建工作</a><a href="/info/1195/25481.htm">关于拟接收党员的公示</a><span>2026-09-17</span></li></ul>'
    assert [i.url for i in parse_list_html(html, "https://fixture.test/list.htm")] == ["https://fixture.test/info/1195/25481.htm"]


def test_explicit_vsb_jsp_article_identity_excludes_adjacent_section_link():
    href = '/nry.jsp?urltype=news.NewsContentUrl&amp;wbtreeid=1195&amp;wbnewsid=24248'
    html = f'<ul class="list"><li><a href="{href}">发展对象公示</a><a href="/djgz.htm">[党建工作]</a>2024-12-30</li></ul>'
    items = parse_list_html(html, "https://fixture.test/list.htm")
    assert len(items) == 1 and items[0].url == "https://fixture.test/nry.jsp?urltype=news.NewsContentUrl&wbtreeid=1195&wbnewsid=24248"
    assert items[0].publish_date == date(2024, 12, 30)


@pytest.mark.parametrize("query", [
    "urltype=tree.TreeTempUrl&wbtreeid=1195&wbnewsid=24248",
    "urltype=news.NewsContentUrl&wbtreeid=1195",
    "urltype=news.NewsContentUrl&wbtreeid=1195&wbnewsid=abc",
    "urltype=news.NewsContentUrl&wbtreeid=1195&wbnewsid=24248&wbnewsid=2",
])
def test_generic_jsp_and_invalid_vsb_identity_are_not_notices(query):
    assert not parse_list_html(f'<ul><li><a href="/nry.jsp?{query}">入口</a>2024-12-30</li></ul>', "https://fixture.test/list.htm")


@pytest.mark.parametrize("denial", ["您无权访问此页面", "您没有访问此页面的权限"])
def test_old_vsb_article_permission_page_is_explicitly_restricted(denial):
    html = f'<title>系统提示</title><div class="content"><p>{denial}</p></div>'
    with pytest.raises(ValueError, match="HTML_PERMISSION_REQUIRED"):
        parse_detail_html(html, "https://fixture.test/nry.jsp", NoticeCandidate(title="公示", url="https://fixture.test/nry.jsp"))


def test_ordinary_notice_discussing_page_permissions_is_not_an_interstitial():
    html = '<h1>访问权限调整说明</h1><div class="v_news_content">出现“您无权访问此页面”时请联系管理员办理权限。</div>'
    assert parse_detail_html(html, "https://fixture.test/info/1/2.htm", NoticeCandidate(title="访问权限调整说明", url="https://fixture.test/info/1/2.htm")).content


def test_old_vsb_zero_count_table_has_explicit_empty_semantics():
    html = '<div><ul></ul><input name="urltype" value="tree.TreeTempUrl"><script src="/system/resource/js/gotopage.js"></script><table><tr><td id="fanye234969">共0条 0/0</td></tr></table></div>'
    assert is_empty_notice_list(html) and not parse_list_html(html, "https://fixture.test/list.htm")


@pytest.mark.asyncio
async def test_isolated_sample_replay_does_not_mistake_retention_for_identity_merge(tmp_path):
    from scripts.validate_jlu_b5_c import database_rounds
    samples = [NoticeCandidate(title="历史招聘通知", url="https://fixture.test/info/1/1.htm", publish_date=date(2013, 10, 1), content="保留历史样本以核对通知身份和用户状态")]
    result = await database_rounds(samples, "old-notice-test", tmp_path, retain_all_samples=True)
    assert result["passed"] and result["notice_count"] == 1 and not result["unexpected_merge_requires_review"]


def test_previous_next_article_title_never_overrides_this_article_heading():
    html = '<title>东北亚学院卓越人才奖评选结果公示-东北亚学院</title><form name="_newscontent_fromname"><div class="ar_title"><h3>东北亚学院卓越人才奖评选结果公示</h3><h6>日期：2025-09-25</h6></div><div class="v_news_content">本次评选结果与申请说明。</div><div class="title">下一条：公 示</div></form>'
    parsed = parse_detail_html(html, "https://fixture.test/info/1/2.htm", NoticeCandidate(title="东北亚学院卓越人才奖...", url="https://fixture.test/info/1/2.htm"))
    assert parsed.title == "东北亚学院卓越人才奖评选结果公示"


@pytest.mark.asyncio
@pytest.mark.parametrize("kinds", [("学业", "国家"), ("国家", "国家励志")])
async def test_distinct_scholarship_programs_are_not_fuzzy_merged(kinds, tmp_path):
    from scripts.validate_jlu_b5_c import database_rounds
    samples = [NoticeCandidate(title=f"吉林大学材料科学与工程学院2026年度研究生{kind}奖学金评审工作实施细则公示", url=f"https://fixture.test/info/1/{i}.htm", publish_date=date(2026, 10, 14), content=f"{kind}奖学金独立评审规则。") for i, kind in enumerate(kinds, 1)]
    result = await database_rounds(samples, "scholarship-distinction-test", tmp_path, retain_all_samples=True)
    assert result["passed"] and result["notice_count"] == 2 and not result["unexpected_merge_requires_review"]


@pytest.mark.parametrize("fallback_date", [None, date(2020, 1, 1)])
def test_hospital_scoped_title_publication_and_body_ignore_event_dates(fallback_date):
    html = (FIXTURES / "hospital.detail.html").read_text(encoding="utf-8")
    parsed = parse_detail_html(html, "https://www.zrlyyy.com/wujia_detail_g7yU_62/177728.html",
        NoticeCandidate(title="关于因停电暂停...", url="https://www.zrlyyy.com/wujia_detail_g7yU_62/177728.html", publish_date=fallback_date))
    assert parsed.title == "关于因停电暂停官网服务的通知"
    assert parsed.publish_date == date(2026, 5, 8)
    assert "各科室、各院区" in parsed.content and "点击数" not in parsed.content


@pytest.mark.asyncio
async def test_preview_reports_empty_without_rendering_or_fetching_navigation():
    html = (FIXTURES / "hospital.empty.html").read_text(encoding="utf-8")
    source = GenericPublicSource({"code": "empty-fixture", "name": "空栏目", "base_url": "https://fixture.test/list.htm"})
    await source.fetcher.close()
    class OnePage:
        async def get(self, url):
            assert url == source.base_url
            return html, "text/html", url
        async def close(self):
            pass
    source.fetcher = OnePage()
    try:
        with pytest.raises(Exception, match="HTML_LIST_EMPTY"):
            await source.fetch_list()
    finally:
        await source.close()
