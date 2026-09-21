from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
from app.__main__ import build_parser
from app.api.source_management import _serialize_source
from app.api.routes import sources as list_sources
from app.config import load_yaml
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Notice, NotificationEvent, NotificationPreference, Source
from app.schemas.notice import NoticeCandidate
from app.sources.registry import SOURCE_TYPES
from app.sources.oa_public import (
    OAPublicSource,
    parse_oa_attachment_references,
    parse_oa_detail_html,
    parse_oa_home_list_url,
    parse_oa_list_html,
)
from app.sources.base import SourceError
import app.sources.oa_public as oa_public_module


FIXTURES = Path(__file__).parent / "fixtures"


def oa_config() -> dict:
    return dict(next(item for item in load_yaml("sources.yaml")["sources"] if item["code"] == "oa"))


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_oa_config_is_official_public_and_registered() -> None:
    config = oa_config()
    assert config["name"] == "吉林大学 OA 校内通知"
    assert config["enabled"] is True
    assert config["ownership"] == "OFFICIAL_CLOUD"
    assert config["source_type"] == "official"
    assert config["auth_required"] is False
    assert config["auth_type"] == "none"
    assert config["execution"] == "cloud"
    assert config["cloud_policy"] == "force_enabled"
    assert SOURCE_TYPES["oa"] is OAPublicSource
    assert SOURCE_TYPES["oa_public"] is OAPublicSource
    with pytest.raises(SystemExit):
        build_parser().parse_args(["oa-login"])


def test_oa_home_discovers_public_internal_notice_list() -> None:
    html = (FIXTURES / "oa_home.html").read_text(encoding="utf-8")
    assert parse_oa_home_list_url(html, "https://oa.jlu.edu.cn/defaultroot/login.jsp") == (
        "https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577"
    )


def test_oa_notice_list_extracts_id_title_url_publisher_and_time() -> None:
    html = (FIXTURES / "oa_list.html").read_text(encoding="utf-8")
    items = parse_oa_list_html(
        html,
        "https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577",
        today=date(2026, 9, 12),
    )
    assert [item.public_id for item in items] == ["oa-70232663", "oa-70184458", "oa-70157806"]
    assert items[0] == NoticeCandidate(
        public_id="oa-70232663",
        title="关于印发《吉林大学2027年推荐免试攻读研究生招生录取工作办法》的通知",
        url=(
            "https://oa.jlu.edu.cn/defaultroot/"
            "PortalInformation!getInformation.action?id=70232663&channelId=179577"
        ),
        publish_date=date(2026, 9, 12),
        publisher="研究生院",
        section="校内通知",
    )
    assert items[1].publish_date == date(2026, 9, 11)
    assert items[1].title == "关于外语水平考试报名工作的通知"
    assert items[2].publish_date == date(2026, 9, 9)


def test_oa_detail_extracts_title_date_publisher_and_clean_body() -> None:
    html = (FIXTURES / "oa_detail.html").read_text(encoding="utf-8")
    fallback = NoticeCandidate(
        public_id="oa-70232663",
        title="列表标题",
        url="https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?id=70232663&channelId=179577",
        publish_date=date(2026, 9, 12),
        publisher="列表单位",
        section="校内通知",
    )
    result = parse_oa_detail_html(html, fallback.url, fallback)
    assert result.title == "关于印发《吉林大学2027年推荐免试攻读研究生招生录取工作办法》的通知"
    assert result.publish_date == date(2026, 9, 11)
    assert result.publisher == "研究生院"
    assert "请认真贯彻执行" in result.content
    assert "不会进入正文" not in result.content
    assert result.public_id == "oa-70232663"


def test_oa_detail_accepts_legacy_rich_text_container_and_distinguishes_empty_body() -> None:
    fallback = NoticeCandidate(title="列表标题", url="https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?id=70377966&channelId=179577")
    parsed = parse_oa_detail_html(
        "<div class='content_t'>详情标题</div><div id='zoom'><p>第一段</p><table><tr><td>表格正文</td></tr></table></div>",
        fallback.url,
        fallback,
    )
    assert parsed.title == "详情标题"
    assert "第一段" in parsed.content and "表格正文" in parsed.content
    with pytest.raises(SourceError, match="OA_PUBLIC_DETAIL_CONTENT_EMPTY"):
        parse_oa_detail_html("<div id='zoom'><p> </p></div>", fallback.url, fallback)
    with pytest.raises(SourceError, match="OA_PUBLIC_DETAIL_PARSER_FAILED"):
        parse_oa_detail_html("<main>没有 OA 正文容器</main>", fallback.url, fallback)


@pytest.mark.asyncio
async def test_oa_parser_failure_saves_raw_html(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = OAPublicSource(oa_config())
    notice = NoticeCandidate(title="列表标题", url="https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?id=70377966&channelId=179577")

    async def get(_: str) -> str:
        return "<html><body>unrecognized OA template</body></html>"

    monkeypatch.setattr(source, "_get", get)
    monkeypatch.setattr(oa_public_module, "get_cache_dir", lambda: tmp_path)
    try:
        with pytest.raises(SourceError, match="OA_PUBLIC_DETAIL_PARSER_FAILED"):
            await source.fetch_detail(notice)
        assert (tmp_path / "oa-detail-failures" / "70377966.html").read_text(encoding="utf-8") == "<html><body>unrecognized OA template</body></html>"
    finally:
        await source.close()


@pytest.mark.asyncio
async def test_oa_snapshot_write_failure_preserves_parser_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = OAPublicSource(oa_config())
    notice = NoticeCandidate(title="列表标题", url="https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?id=70377966&channelId=179577")

    async def get(_: str) -> str:
        return "<html><body>unrecognized OA template</body></html>"

    monkeypatch.setattr(source, "_get", get)
    monkeypatch.setattr(oa_public_module, "get_cache_dir", lambda: tmp_path / "not-a-directory")
    (tmp_path / "not-a-directory").write_text("blocked", encoding="utf-8")
    try:
        with pytest.raises(SourceError, match="OA_PUBLIC_DETAIL_PARSER_FAILED"):
            await source.fetch_detail(notice)
    finally:
        await source.close()


def test_oa_attachment_parser_extracts_download_reference() -> None:
    html = (FIXTURES / "oa_detail.html").read_text(encoding="utf-8")
    page_url = "https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?id=70232663&channelId=179577"
    references = parse_oa_attachment_references(html, page_url)
    assert len(references) == 1
    assert references[0].stored_name == "2026091119441859008176161.pdf"
    assert references[0].display_name == "附件 《吉林大学2027年推荐免试攻读研究生招生录取工作办法》.pdf"
    assert references[0].encoder_value.endswith("@70232663")


@pytest.mark.asyncio
async def test_oa_adapter_keeps_list_discovery_separate_from_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = OAPublicSource(oa_config())
    list_html = (FIXTURES / "oa_list.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES / "oa_detail.html").read_text(encoding="utf-8")
    requested: list[str] = []

    async def get(url: str) -> str:
        requested.append(url)
        return detail_html if "getInformation.action" in url else list_html

    async def attachment_url(*_: object) -> str:
        return "https://oa.jlu.edu.cn/defaultroot/rd/download/attachdownload.jsp?res=fixture"

    monkeypatch.setattr(source, "_get", get)
    monkeypatch.setattr(source, "_attachment_url", attachment_url)
    try:
        items = await source.fetch_list()
        assert len(items) == 3
        assert requested == [oa_config()["sections"][0]["url"]]
        detail = await source.fetch_detail(items[0])
        assert len(requested) == 2
        assert detail.attachments[0].type == "pdf"
        assert detail.attachments[0].url.endswith("res=fixture")
    finally:
        await source.close()


def test_existing_private_oa_row_is_converted_in_place_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_session() as db:
        source = Source(
            code="oa",
            name="吉林大学 OA",
            base_url="https://oa.jlu.edu.cn",
            enabled=False,
            ownership="CUSTOM_LOCAL_PRIVATE",
            source_type="private_browser",
            parser="oa",
            auth_type="browser_session",
            credential_ref="oa-session-oa",
            login_url="https://oa.jlu.edu.cn/defaultroot/login.jsp",
            session_profile_ref="oa-profile",
            health_state="needs_reauth",
            last_error_code="OA_LOGIN_NOT_CONFIGURED",
            source_scope="private",
            execution="local",
        )
        db.add(source)
        db.commit()
        source_id = source.id
        deleted: list[str] = []
        monkeypatch.setattr(
            runner_module,
            "get_settings",
            lambda: SimpleNamespace(effective_deployment_role="cloud"),
        )
        monkeypatch.setattr(runner_module.credential_store, "delete", deleted.append)

        CrawlerManager._sync_sources(db, [oa_config()])
        converted = db.scalar(select(Source).where(Source.code == "oa"))
        assert converted is not None and converted.id == source_id
        assert converted.name == "吉林大学 OA 校内通知"
        assert converted.ownership == "OFFICIAL_CLOUD"
        assert converted.source_type == "official"
        assert converted.parser == "oa_public"
        assert converted.auth_type == "none"
        assert converted.credential_ref is None and converted.login_url is None
        assert converted.session_profile_ref is None
        assert converted.source_scope == "official" and converted.execution == "cloud"
        assert converted.cloud_source_id == "oa"
        assert converted.cloud_policy == "force_enabled"
        assert converted.enabled is True and converted.validation_status == "passed"
        assert deleted == ["oa-session-oa"]
        serialized = _serialize_source(converted)
        assert serialized["authentication_status"] == "not_required"
        assert serialized["auth_required"] is False
        assert serialized["password_saved"] is False
        assert serialized["login_url"] is None
        summary = next(item for item in list_sources(db) if item["code"] == "oa")
        assert summary["auth_required"] is False
        assert summary["status"] != "login_required"
        assert "登录" not in str(summary["message"] or "")


def test_desktop_oa_uses_cloud_feed_instead_of_fetching_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_session() as db:
        monkeypatch.setattr(
            runner_module,
            "get_settings",
            lambda: SimpleNamespace(
                effective_deployment_role="desktop",
                public_feed_url="https://cloud.example.test/api/public/v1",
            ),
        )
        CrawlerManager._sync_sources(db, [oa_config()])
        config = CrawlerManager._load_source_configs(db)[0]
        source = db.scalar(select(Source).where(Source.code == "oa"))
        assert source is not None
        assert source.ownership == "OFFICIAL_CLOUD"
        assert source.execution == "cloud"
        assert source.parser == "cloud_feed"
        assert config["parser"] == "cloud_feed"
        assert config["content_parser"] == "cloud_feed"
        assert config["public_feed_url"] == "https://cloud.example.test/api/public/v1"
        assert config["cloud_source_id"] == "oa"


@pytest.mark.asyncio
async def test_oa_incremental_second_run_skips_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with make_session() as db:
        source = Source(
            code="oa",
            name="吉林大学 OA 校内通知",
            base_url="https://oa.jlu.edu.cn",
            ownership="OFFICIAL_CLOUD",
            source_type="official",
            parser="oa_public",
            auth_type="none",
            source_scope="official",
            execution="cloud",
            cloud_policy="force_enabled",
        )
        db.add(source)
        db.add(NotificationPreference(id=1, enabled=True))
        db.commit()
        listed = NoticeCandidate(
            public_id="oa-70232663",
            title="OA 公开通知",
            url="https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?id=70232663&channelId=179577",
            publish_date=date(2026, 9, 11),
            publisher="研究生院",
        )

        class FixtureOA:
            detail_calls = 0

            async def fetch_list(self) -> list[NoticeCandidate]:
                return [listed]

            async def fetch_detail(self, item: NoticeCandidate) -> NoticeCandidate:
                self.detail_calls += 1
                return item.model_copy(update={"content": "公开正文"})

            async def close(self) -> None:
                return None

        adapter = FixtureOA()
        monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
        monkeypatch.setattr(runner_module, "build_source", lambda _: adapter)
        manager = CrawlerManager(tmp_path)
        first = await manager._run_source(oa_config(), bootstrap=False)
        second = await manager._run_source(oa_config(), bootstrap=False)
        assert first.new_count == 1 and first.detail_fetched == 1
        assert second.unchanged_count == 1 and second.detail_skipped == 1
        assert second.detail_fetched == 0 and adapter.detail_calls == 1
        assert len(db.scalars(select(Notice)).all()) == 1
        events = db.scalars(select(NotificationEvent)).all()
        assert len(events) == 1
        assert events[0].event_type in {"NEW_NOTICE", "IMPORTANT_NOTICE"}
        assert events[0].route == "/notices/1"
