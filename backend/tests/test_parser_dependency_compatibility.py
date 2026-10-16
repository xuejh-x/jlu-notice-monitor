"""CMS context checks must survive strict relational-selector dependencies."""
from datetime import date

import pytest

from app.parsers import parse_detail_html
from app.schemas.notice import NoticeCandidate


@pytest.mark.parametrize("direct", [True, False])
def test_right_panel_metadata_requires_observed_direct_body_context(direct):
    body = '<div class="view-cnt"><div class="v_news_content">通知正文</div></div>'
    if not direct:
        body = '<section>' + body + '</section>'
    html = '<div class="right-nr"><div class="view-title">正文对应的通知标题</div><div class="view-info">发布时间：2026-10-16</div>' + body + '</div>'
    fallback = NoticeCandidate(title="列表标题", url="https://test.invalid/info/1/2.htm", publish_date=date(2026, 10, 15))
    parsed = parse_detail_html(html, fallback.url, fallback)
    assert parsed.title == ("正文对应的通知标题" if direct else fallback.title)
    assert parsed.publish_date == (date(2026, 10, 16) if direct else fallback.publish_date)


@pytest.mark.parametrize("direct", [True, False])
def test_table_publication_cell_requires_observed_direct_body_context(direct):
    body = '<div id="vsb_content"><div class="v_news_content">通知正文</div></div>'
    if not direct:
        body = '<section>' + body + '</section>'
    html = '<table><tr><td class="pubtime_publisher">发布时间：2026-10-16</td></tr><tr><td class="content">' + body + '</td></tr></table>'
    fallback = NoticeCandidate(title="列表标题", url="https://test.invalid/info/1/2.htm", publish_date=date(2026, 10, 15))
    parsed = parse_detail_html(html, fallback.url, fallback)
    assert parsed.publish_date == (date(2026, 10, 16) if direct else fallback.publish_date)
