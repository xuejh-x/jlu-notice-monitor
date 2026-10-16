"""B7 real metadata controls: recover truncated titles and publication dates safely."""
from datetime import date
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.parsers import parse_detail_html
from app.schemas.notice import NoticeCandidate

FIXTURES = Path(__file__).parent / "fixtures/jlu_b7"
CONTROLS = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def preserve_audit_helper_environment():
    with patch.dict(os.environ, os.environ.copy(), clear=True):
        yield


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c["name"])
def test_real_article_header_restores_title_and_overrides_stale_list_date(control):
    raw = (FIXTURES / control["file"]).read_text(encoding="utf-8")
    fallback = NoticeCandidate(title=control["title"][:8] + "...", url=control["url"], publish_date=date(2001, 1, 1))
    parsed = parse_detail_html(raw, control["url"], fallback)
    assert parsed.title == control["title"]
    assert parsed.publish_date == (date.fromisoformat(control["date"]) if control["date"] else date(2001, 1, 1))


@pytest.mark.parametrize("header", [
    '<div class="content-bt">错误导航标题</div>',
    '<div class="readtitle">错误导航标题</div>',
    '<div class="t"><p class="ti">错误导航标题</p><p class="author"><span>2099-01-01</span></p></div>',
    '<div class="wzxxys">时间：2099-01-01</div>',
])
def test_named_metadata_in_navigation_or_body_never_overrides_article(header):
    raw = '<form name="_newscontent_fromname"><nav>' + header + '</nav><h1>正常通知标题</h1><div class="v_news_content">正文' + header + '</div></form>'
    parsed = parse_detail_html(raw, "https://test.invalid/info/1/2.htm", NoticeCandidate(title="正常通知标题", url="https://test.invalid/info/1/2.htm", publish_date=date(2026, 10, 15)))
    assert parsed.title == "正常通知标题"
    assert parsed.publish_date == date(2026, 10, 15)


def test_bare_author_header_requires_single_date_and_no_body_or_update_time():
    raw = '<form name="_newscontent_fromname"><div class="t"><p class="ti">标题</p><p class="author"><span>更新时间：2027-01-01</span><span>2026-01-01</span><span>2026-02-01</span></p></div><div class="v_news_content">活动日期：2028-01-01</div></form>'
    parsed = parse_detail_html(raw, "https://test.invalid/info/1/2.htm", NoticeCandidate(title="标题", url="https://test.invalid/info/1/2.htm", publish_date=date(2025, 1, 1)))
    assert parsed.publish_date == date(2025, 1, 1)


def test_real_wordpress_article_attachments_exclude_tags_and_site_footer():
    control = next(c for c in CONTROLS if c["name"] == "wordpress")
    html = (FIXTURES / control["file"]).read_text(encoding="utf-8") + '<footer><h4>相关附件:1</h4><ul><li><a href="/footer.pdf">站点页脚.pdf</a></li></ul></footer>'
    parsed = parse_detail_html(html, control["url"], NoticeCandidate(title=control["title"], url=control["url"]))
    assert len(parsed.attachments) == 4
    assert {a.type for a in parsed.attachments} == {"pdf", "doc"}
    assert all("/attachment/2025/09/" in a.url for a in parsed.attachments)
    assert "相关附件" not in parsed.content


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", json.loads((FIXTURES / "admission-identity.json").read_text(encoding="utf-8")), ids=lambda s: s["id"])
async def test_real_admissions_stages_and_explicit_batch_remain_distinct(sample, tmp_path):
    from scripts.validate_jlu_b5_c import database_rounds
    details = [NoticeCandidate.model_validate(d) for d in sample["samples"]]
    result = await database_rounds(details, "b7-identity-" + sample["id"], tmp_path, retain_all_samples=True)
    assert result["passed"] and result["notice_count"] == len(details)
    assert not result["unexpected_merge_requires_review"]


def test_wordpress_iso_datetime_is_used_without_guessing_us_display_date():
    from app.sources.generic import parse_configured_html
    html = '<article><h2><a href="/2026/09/1.html">通知标题</a></h2><time datetime="2026-09-03T10:00:00+00:00">09/03/2026</time></article>'
    items = parse_configured_html(html, "https://test.invalid/list", {"item_selector": "article", "title_selector": "h2 a", "url_selector": "h2 a", "time_selector": "time"})
    assert items[0].publish_date == date(2026, 9, 3)


def test_fake_nav01_menu_cannot_override_article_metadata():
    raw = '<form name="_newscontent_fromname"><div class="nav01"><h3>错误菜单标题</h3><h6><div class="ll"><span>时间：2099-01-01</span><a href="/login">菜单</a></div></h6></div><div class="v_news_content">正文</div></form>'
    parsed = parse_detail_html(raw, "https://test.invalid/info/1/2.htm", NoticeCandidate(title="正确标题", url="https://test.invalid/info/1/2.htm", publish_date=date(2026, 10, 15)))
    assert parsed.title == "正确标题" and parsed.publish_date == date(2026, 10, 15)


@pytest.mark.parametrize("target,allowed", [
    ("https://synlab.jlu.edu.cn/archive/information/events/page/2", True),
    ("https://synlab.jlu.edu.cn/archive/information/events/page/3/", True),
    ("https://synlab.jlu.edu.cn/archive/information/events/instrument-announcement", False),
    ("https://synlab.jlu.edu.cn/archive/information/events/page/0", False),
    ("https://synlab.jlu.edu.cn/archive/information/events/page/../other", False),
    ("https://synlab.jlu.edu.cn/archive/information/events/other/page/2", False),
    ("https://synlab.jlu.edu.cn/archive/information/events/page/2?cid=other", False),
    ("http://synlab.jlu.edu.cn/archive/information/events/page/2", False),
    ("https://other.invalid/archive/information/events/page/2", False),
    ("https://user:password@synlab.jlu.edu.cn/archive/information/events/page/2", False),
])
def test_observed_wordpress_pagination_keeps_origin_column_and_query_boundaries(target, allowed):
    from app.services.list_pagination import ListPagination
    pager = ListPagination("https://synlab.jlu.edu.cn/archive/information/events", {"pagination_limit": 2, "next_page_selector": "a.next.page-numbers"}, max_pages=3, items_per_section=30)
    assert pager.within_column(target) is allowed


def test_official_talent_recruitment_link_is_discovered_without_article_or_file_links():
    from scripts.audit_jlu_sites import column_links
    html = '<a href="../lxwm/rczp.htm">人才招聘</a><a href="/info/1/2.htm">人才招聘公告</a><a href="/job.pdf">人才招聘</a>'
    assert column_links(html, "https://press.jlu.edu.cn/lxwm/lxfs.htm") == {"https://press.jlu.edu.cn/lxwm/rczp.htm": "人才招聘"}


@pytest.mark.parametrize("html", [
    '<form name="_newscontent_fromname"><div class="v_news_content">正文</div><div><h1>附加标题</h1><div align="center">时间：2099-01-01</div></div></form>',
    '<div class="right-nr"><div class="view-cnt"><div class="v_news_content">正文</div></div><div class="view-info">发布时间：2099-01-01</div></div>',
    '<table><tr><td class="content"><div id="vsb_content"><div class="v_news_content">正文</div></div></td></tr><tr><td class="pubtime_publisher">发布时间：2099-01-01</td></tr></table>',
])
def test_b7_metadata_after_body_does_not_override_publication_date(html):
    parsed = parse_detail_html(html, "https://test.invalid/info/1/2.htm", NoticeCandidate(title="正确标题", url="https://test.invalid/info/1/2.htm", publish_date=date(2026, 10, 15)))
    assert parsed.publish_date == date(2026, 10, 15)
