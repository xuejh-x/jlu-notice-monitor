from datetime import date
import importlib
from pathlib import Path

import pytest

from app.parsers import parse_detail_html, parse_list_html
from app.schemas.notice import NoticeCandidate
from app.sources.generic import parse_configured_html


@pytest.mark.parametrize("label", ["更新时间", "更新日期", "修改时间", "最后修改时间"])
@pytest.mark.parametrize("configured", [False, True])
def test_explicit_update_label_is_not_a_list_publication_date(label, configured):
    html = f'<ul class="list"><li><a href="/info/1002/3520.htm">测试通知</a><span class="date">{label}：2026-06-25</span></li></ul>'
    url = "https://fixture.test/index/tzgg.htm"
    items = parse_configured_html(html, url, {"item_selector": ".list li", "time_selector": ".date"}) if configured else parse_list_html(html, url)
    assert len(items) == 1 and items[0].publish_date is None


@pytest.mark.parametrize("configured", [False, True])
def test_explicit_publication_label_wins_over_previous_update_label(configured):
    html = '<ul class="list"><li><a href="/info/1/1.htm">测试通知</a><span class="date">更新时间：2026-10-14 发布时间：2026-06-25</span></li></ul>'
    url = "https://fixture.test/list.htm"
    items = parse_configured_html(html, url, {"item_selector": ".list li", "time_selector": ".date"}) if configured else parse_list_html(html, url)
    assert items[0].publish_date == date(2026, 6, 25)


def test_datetime_attribute_does_not_hide_a_visible_update_label():
    html = '<ul class="list"><li><a href="/info/1/1.htm">测试通知</a><time datetime="2026-06-25">更新时间：2026-06-25</time></li></ul>'
    assert parse_list_html(html, "https://fixture.test/list.htm")[0].publish_date is None


@pytest.fixture
def assessor(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    return importlib.import_module("jlu_date_evidence").assess_dates


def test_actual_yzb_update_only_fixture_remains_unconfirmed_even_when_dates_equal(assessor):
    html = (Path(__file__).parent / "fixtures/jlu_b4/yzb-notices.detail.html").read_text(encoding="utf-8")
    item = NoticeCandidate(title="测试", url="https://fixture.test/info/1002/3520.htm", publish_date=date(2026, 6, 25))
    parsed = parse_detail_html(html, item.url, item)
    result = assessor(html, list_date=item.publish_date, parsed_date=parsed.publish_date)
    assert result["list_matches_update"] and not result["publication_verified"]
    assert result["verdict"] == "UPDATE_TIME_ONLY_PUBLICATION_UNCONFIRMED"
    assert parsed.publish_date == item.publish_date  # Preserve the existing fallback contract.


@pytest.mark.parametrize("prefix", ["", "<meta property='article:published_time' content='2026-06-25'>"])
def test_body_event_dates_and_generic_head_dates_do_not_establish_publication(assessor, prefix):
    html = f'<head>{prefix}<meta name="date" content="2026-06-27"></head><form name="_newscontent_fromname"><div class="arc-info">更新时间:2026-06-26</div><div class="v_news_content">发布日期：2026-06-28；活动日期：2026-09-05</div></form>'
    result = assessor(html, parsed_date=date(2026, 6, 25))
    assert result["publication_verified"] == bool(prefix)
    assert result["body_dates_used_as_publication"] is False


def test_conflicting_publication_metadata_does_not_pass(assessor):
    html = '<head><meta name="pubdate" content="2026-06-25"></head><form name="_newscontent_fromname"><p class="meta">发布时间：2026-06-26</p><div class="v_news_content">通知正文。</div></form>'
    result = assessor(html, parsed_date=date(2026, 6, 25))
    assert result["verdict"] == "CONFLICTING_PUBLICATION_EVIDENCE" and not result["publication_verified"]


def test_invalid_publication_metadata_does_not_pass(assessor):
    html = '<head><meta name="pubdate" content="2026-02-30"></head><div class="v_news_content">通知正文。</div>'
    result = assessor(html)
    assert result["invalid_evidence"] and not result["publication_verified"]
