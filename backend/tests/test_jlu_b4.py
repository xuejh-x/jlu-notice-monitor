from __future__ import annotations
from datetime import date
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from app.parsers import parse_detail_html
from app.schemas.notice import NoticeCandidate
from app.sources.base import SourceError
from app.sources.generic import GenericPublicSource, parse_configured_html

FIXTURES = Path(__file__).parent / "fixtures/jlu_b4"
CONTROLS = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
CONFIG = {"item_selector": ".m-list-line_content", "title_selector": "h3 a[title]",
          "url_selector": "h3 a[href*='/portal/jyzp/article/details?id=']", "time_selector": "span:last-child"}


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c["name"])
def test_real_employment_lists_preserve_ids_and_creation_dates(control):
    items = parse_configured_html((FIXTURES / (control["name"] + ".list.html")).read_text(encoding="utf-8"), control["url"], CONFIG)
    assert len(items) == 3
    assert [item.url for item in items] == [d["url"] for d in control["details"]]
    assert all(item.publish_date and item.publish_date.year == 2026 for item in items)
    assert all("2027-01-01" not in item.title and not item.title.startswith("[置顶]") for item in items)
    assert all(len(parse_qs(urlsplit(item.url).query)["id"][0]) == 32 for item in items)
    assert parse_qs(urlsplit(control["url"]).query)["cid"][0] in {"jyzp_tzgg", "jyzp_gs"}


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c["name"])
def test_real_employment_detail_title_date_body_and_attachment_contract(control):
    items = parse_configured_html((FIXTURES / (control["name"] + ".list.html")).read_text(encoding="utf-8"), control["url"], CONFIG)
    for item, d in zip(items, control["details"]):
        html = (FIXTURES / d["file"]).read_text(encoding="utf-8")
        parsed = parse_detail_html(html, item.url, item.model_copy(update={"title": "截断的标题...", "publish_date": date(2027, 1, 1)}))
        assert parsed.title == item.title and parsed.publish_date == item.publish_date
        assert parsed.content.startswith("离线正文")
        for attachment in parsed.attachments:
            assert attachment.type in {"pdf", "docx", "xlsx", "doc", "xls"}
            assert attachment.filename.endswith("." + attachment.type) and " MB)" not in attachment.filename
            assert set(attachment.model_dump()) == {"filename", "url", "type"}
            assert parse_qs(urlsplit(attachment.url).query).get("id")


@pytest.mark.asyncio
@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c["name"])
async def test_actual_generic_entry_points_work_with_selectors_and_do_not_download_files(control, monkeypatch):
    async def allow(url, **kwargs):
        return url
    monkeypatch.setattr("app.sources.generic.validate_source_url", allow)
    source = GenericPublicSource({"code": "candidate", "name": "Candidate", "base_url": control["url"], "parser_config": CONFIG})
    requested = []
    async def get(url):
        requested.append(url)
        name = control["name"] + ".list.html" if url == control["url"] else next(d["file"] for d in control["details"] if d["url"] == url)
        return (FIXTURES / name).read_text(encoding="utf-8"), "text/html", url
    source.fetcher.get = get
    try:
        items = await source.fetch_list()
        assert len(items) == 3
        for item in items:
            assert (await source.fetch_detail(item)).content.startswith("离线正文")
        assert len(requested) == 4 and all("downloadFile" not in url for url in requested)
    finally:
        await source.close()


def test_employment_selector_never_promotes_other_portal_links():
    html = '<nav><a href="/portal/jyzp/article/details?id=nav">首页</a></nav><div class="m-list-line_content"><h3><a href="/portal/jobs/list">招聘列表</a></h3><span>创建时间2026-10-14</span></div>'
    with pytest.raises(SourceError, match="did not find"):
        parse_configured_html(html, "https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_gs", CONFIG)


def test_creation_time_is_not_inferred_in_unrelated_metadata_or_body():
    html = '<h1>测试通知</h1><div class="meta">系统创建时间：2027-01-01</div><div class="v_news_content">创建时间：2027-01-02</div>'
    item = NoticeCandidate(title="测试通知", url="https://fixture.test/info/1/1.htm")
    assert parse_detail_html(html, item.url, item).publish_date is None


def test_centered_body_subheading_cannot_replace_article_title():
    html = '<form name="_newscontent_fromname"><h1>真实文章标题</h1><div class="v_news_content"><h2 align="center">正文小标题</h2>通知正文</div></form>'
    item = NoticeCandidate(title="真实文章标题", url="https://fixture.test/info/1/1.htm")
    assert parse_detail_html(html, item.url, item).title == "真实文章标题"


@pytest.mark.parametrize("ident", ["kjc", "hssra", "youth"])
def test_observed_research_and_youth_templates_enrich_title_and_publication_date(ident):
    controls = json.loads((FIXTURES / "vsb-manifest.json").read_text(encoding="utf-8"))
    control = next(c for c in controls if c["id"] == ident)
    parsed = parse_detail_html((FIXTURES / control["file"]).read_text(encoding="utf-8"), control["url"],
                               NoticeCandidate(title="截断标题...", url=control["url"]))
    assert parsed.title == control["title"]
    assert str(parsed.publish_date) == control["date"]


@pytest.fixture
def verifier_module(monkeypatch, tmp_path):
    import importlib
    for name, value in {"JLU_DATABASE_URL": "sqlite://", "JLU_APP_DATA_DIR": str(tmp_path),
                        "JLU_SCHEDULER_ENABLED": "false", "JLU_STARTUP_SYNC_ENABLED": "false"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    return importlib.import_module("validate_jlu_b4")


def test_update_time_does_not_become_verified_publication_metadata(verifier_module):
    control = next(c for c in json.loads((FIXTURES / "vsb-manifest.json").read_text(encoding="utf-8")) if c["id"] == "yzb-notices")
    html = (FIXTURES / control["file"]).read_text(encoding="utf-8")
    parsed = parse_detail_html(html, control["url"], NoticeCandidate(title=control["title"], url=control["url"]))
    assert parsed.publish_date is None
    evidence = verifier_module.inspect_sample(html, control["url"], parsed)
    assert not evidence["date_verified"] and evidence["date_semantics"] == "UPDATE_TIME_ONLY_PUBLICATION_UNCONFIRMED"
    assert "SITE_DATE_IS_UPDATE_TIME" in evidence["issues"]


def test_body_crosscheck_preserves_text_when_original_image_urls_are_added(verifier_module):
    html = '<form name="_newscontent_fromname"><h1>测试标题</h1><p class="meta">发布日期：2026-10-14</p><div class="v_news_content"><p>前文</p><img src="/notice.jpg"><p>后文</p></div></form>'
    url = "https://fixture.test/info/1/1.htm"
    parsed = parse_detail_html(html, url, NoticeCandidate(title="测试标题", url=url))
    assert verifier_module.inspect_sample(html, url, parsed)["body_verified"]


@pytest.mark.asyncio
async def test_permission_page_is_not_misreported_as_empty_or_selector_failure(verifier_module):
    url = "https://fixture.test/list.jsp?wbtreeid=1402"
    class Fetch:
        async def get(self, target):
            return {"time": "fixture-time", "ok": True, "final_url": target, "html_path": "fixture.html", "sha256": "fixture-sha",
                    "status": 200, "html": (FIXTURES / "permission-required.html").read_text(encoding="utf-8-sig")}
    candidate = {"id": "fixture", "institution": "Fixture", "column": "Fixture", "discovery_url": "fixture",
                 "config": {"base_url": url, "enabled": False, "auth_type": "none", "allow_private_network": False}}
    result = await verifier_module.validate(Fetch(), candidate)
    assert result["status"] == "需认证" and result["verdict"] == "PERMISSION_RESTRICTED"
    assert result["details"] == [] and result["enabled"] is False
