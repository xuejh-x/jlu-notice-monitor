from pathlib import Path

from app.parsers import parse_detail_html, parse_list_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_parser_extracts_articles_and_dates() -> None:
    html = (FIXTURES / "list.html").read_text(encoding="utf-8")
    items = parse_list_html(html, "https://ccst.jlu.edu.cn/rcpy/list.htm", "教学通知")
    assert len(items) == 2
    assert items[0].title == "第42次CCF CSP认证报名通知"
    assert items[0].publish_date.isoformat() == "2026-08-26"
    assert items[0].url == "https://ccst.jlu.edu.cn/info/1056/21001.htm"


def test_detail_parser_extracts_body_and_attachment() -> None:
    list_html = (FIXTURES / "list.html").read_text(encoding="utf-8")
    fallback = parse_list_html(list_html, "https://ccst.jlu.edu.cn/rcpy/list.htm")[0]
    detail_html = (FIXTURES / "detail.html").read_text(encoding="utf-8")
    item = parse_detail_html(detail_html, fallback.url, fallback)
    assert "全日制本科生" in item.content
    assert item.publisher == "教务办"
    assert item.publish_date.isoformat() == "2026-08-26"
    assert item.attachments[0].type == "xlsx"
    assert item.attachments[0].url.startswith("https://ccst.jlu.edu.cn/__local/")

