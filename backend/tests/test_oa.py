from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.__main__ import build_parser
import app.api.source_management as source_management
import app.crawler.runner as runner_module
from app.config import BACKEND_DIR, load_yaml
from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Attachment, Notice, NoticeSourceRelation, Source
from app.schemas.notice import NoticeCandidate
from app.sources.base import LoginExpiredError, SourceError, SourceNotConfiguredError
from app.sources.oa import OASource, sanitize_oa_url


def oa_config(*, configured: bool = False) -> dict:
    config = dict(next(item for item in load_yaml("sources.yaml")["sources"] if item["code"] == "oa"))
    if configured:
        config["parser_config"] = {
            "item_selector": ".notice-item",
            "title_selector": ".notice-title",
            "link_selector": ".notice-title",
            "date_selector": "time",
            "content_selector": ".notice-body",
            "attachment_selector": ".attachment",
        }
    return config


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_oa_is_disabled_and_profile_is_local_data() -> None:
    config = oa_config()
    source = OASource(config)
    assert config["enabled"] is False
    assert config["dedup_across_sources"] is True
    assert source.profile_path == BACKEND_DIR / "data" / "browser_profile" / "oa"


def test_oa_login_command_is_registered() -> None:
    assert build_parser().parse_args(["oa-login"]).command == "oa-login"
    assert hasattr(OASource, "login_setup")
    assert hasattr(OASource, "check_login")


@pytest.mark.asyncio
async def test_oa_reauthentication_uses_owned_browser_coordinator(
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
            health_state="unconfigured",
        )
        db.add(source)
        db.commit()
        started: list[tuple[int, dict]] = []
        monkeypatch.setattr(
            source_management.oa_login_coordinator,
            "start",
            lambda source_id, config: started.append((source_id, config)) or True,
        )
        result = await source_management.reauthenticate(source.id, db)
        assert result["status"] == "login_window_opened"
        assert started[0][0] == source.id and started[0][1]["parser"] == "oa"
        db.refresh(source)
        assert source.health_state == "needs_reauth"
        assert source.credential_ref is None


@pytest.mark.asyncio
async def test_oa_reauthentication_preflight_failure_preserves_source_state(
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
            health_state="unconfigured",
        )
        db.add(source)
        db.commit()

        def unavailable(*_: object, **__: object) -> bool:
            raise SourceError("OA_BROWSER_RUNTIME_UNAVAILABLE")

        monkeypatch.setattr(source_management.oa_login_coordinator, "start", unavailable)
        with pytest.raises(HTTPException) as exc_info:
            await source_management.reauthenticate(source.id, db)
        assert exc_info.value.status_code == 503
        db.refresh(source)
        assert source.health_state == "unconfigured"
        assert source.reauth_notified_at is None


@pytest.mark.asyncio
async def test_oa_not_configured_is_not_reported_as_auth_failure() -> None:
    source = OASource(oa_config())
    with pytest.raises(SourceNotConfiguredError, match="OA_PARSER_UNCONFIGURED"):
        await source.fetch_list()


@pytest.mark.asyncio
async def test_oa_not_configured_is_skipped_without_poisoning_other_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = make_session()
    db.add(
        Source(
            code="oa",
            name="吉林大学 OA",
            base_url="https://oa.jlu.edu.cn",
            enabled=True,
            ownership="CUSTOM_LOCAL_PRIVATE",
            source_type="private_browser",
            parser="oa",
            auth_type="browser_session",
            health_state="needs_reauth",
        )
    )
    db.commit()

    class UnconfiguredOA:
        async def fetch_list(self) -> list[NoticeCandidate]:
            raise SourceNotConfiguredError("OA_PARSER_UNCONFIGURED")

        async def close(self) -> None:
            return None

    monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(runner_module, "build_source", lambda _: UnconfiguredOA())
    result = await CrawlerManager(tmp_path)._run_source(oa_config(), bootstrap=False)

    assert result.status == "skipped"
    assert result.errors == ["OA_PARSER_UNCONFIGURED"]
    persisted = db.scalar(select(Source).where(Source.code == "oa"))
    assert persisted is not None
    assert persisted.health_state == "unconfigured"
    assert persisted.last_error_code == "OA_PARSER_UNCONFIGURED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("detail_error", "expected_status", "expected_health", "expected_code"),
    [
        (
            SourceNotConfiguredError("OA_CONTENT_SELECTOR_MISSING"),
            "skipped",
            "unconfigured",
            "OA_CONTENT_SELECTOR_MISSING",
        ),
        (LoginExpiredError("OA_LOGIN_EXPIRED"), "failure", "needs_reauth", "AUTH_EXPIRED"),
    ],
)
async def test_oa_detail_state_errors_escape_per_notice_isolation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    detail_error: SourceError,
    expected_status: str,
    expected_health: str,
    expected_code: str,
) -> None:
    db = make_session()
    db.add(
        Source(
            code="oa",
            name="吉林大学 OA",
            base_url="https://oa.jlu.edu.cn",
            enabled=True,
            ownership="CUSTOM_LOCAL_PRIVATE",
            source_type="private_browser",
            parser="oa",
            auth_type="browser_session",
            health_state="authenticated",
        )
    )
    db.commit()

    class DetailStateOA:
        async def fetch_list(self) -> list[NoticeCandidate]:
            return [
                NoticeCandidate(
                    title="OA 测试通知",
                    url="https://oa.jlu.edu.cn/notice?id=1",
                    publish_date=date(2026, 9, 10),
                )
            ]

        async def fetch_detail(self, _: NoticeCandidate) -> NoticeCandidate:
            raise detail_error

        async def close(self) -> None:
            return None

    monkeypatch.setattr(runner_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(runner_module, "build_source", lambda _: DetailStateOA())
    result = await CrawlerManager(tmp_path)._run_source(
        oa_config(configured=True), bootstrap=False
    )

    assert result.status == expected_status
    persisted = db.scalar(select(Source).where(Source.code == "oa"))
    assert persisted is not None
    assert persisted.health_state == expected_health
    assert persisted.last_error_code == expected_code


@pytest.mark.asyncio
async def test_oa_session_expired_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    source = OASource(oa_config(configured=True))

    async def login_page(*_: object, **__: object) -> tuple[str, str, str]:
        return "<html></html>", "https://oa.jlu.edu.cn/defaultroot/login.jsp", "用户登录"

    monkeypatch.setattr(source, "_page_snapshot", login_page)
    with pytest.raises(LoginExpiredError, match="OA_LOGIN_EXPIRED"):
        await source.fetch_list()


@pytest.mark.asyncio
async def test_oa_authenticated_adapter_parses_list_detail_and_safe_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = OASource(oa_config(configured=True))
    list_html = """
      <ul><li class="notice-item"><a class="notice-title"
      href="/notice/view?id=7&token=list-secret">OA 奖学金通知</a>
      <time>2026-09-10</time></li></ul>
    """
    detail_html = """
      <article class="notice-body">请于 9 月 20 日前提交申请。</article>
      <a class="attachment" href="/download?id=9&ticket=attachment-secret">申请表.docx</a>
    """
    requested: list[str] = []

    async def snapshot(url: str, **_: object) -> tuple[str, str, str]:
        requested.append(url)
        if "/notice/view" in url:
            return detail_html, url, "请于 9 月 20 日前提交申请。"
        return list_html, "https://oa.jlu.edu.cn/notices", "校内通知"

    monkeypatch.setattr(source, "_page_snapshot", snapshot)
    items = await source.fetch_list()
    assert items == [
        NoticeCandidate(
            title="OA 奖学金通知",
            url="https://oa.jlu.edu.cn/notice/view?id=7",
            publish_date=date(2026, 9, 10),
            section="校内通知",
        )
    ]
    detail = await source.fetch_detail(items[0])
    assert "token=list-secret" in requested[-1]
    assert detail.content == "请于 9 月 20 日前提交申请。"
    assert detail.attachments[0].filename == "申请表.docx"
    assert detail.attachments[0].type == "docx"
    assert detail.attachments[0].url == "https://oa.jlu.edu.cn/download?id=9"
    assert "secret" not in repr(detail)


def test_oa_sensitive_urls_are_redacted_before_diagnostics_or_storage() -> None:
    safe = sanitize_oa_url(
        "https://oa.jlu.edu.cn/download?id=3&token=do-not-log&ticket=also-secret#fragment"
    )
    assert safe == "https://oa.jlu.edu.cn/download?id=3"
    assert "do-not-log" not in safe and "also-secret" not in safe


def test_oa_notice_uses_cross_source_dedup_and_unified_attachment_pipeline() -> None:
    with make_session() as db:
        public = Source(code="jwc", name="本科生院", base_url="https://jwc.jlu.edu.cn")
        oa = Source(
            code="oa",
            name="吉林大学 OA",
            base_url="https://oa.jlu.edu.cn",
            ownership="CUSTOM_LOCAL_PRIVATE",
        )
        db.add_all([public, oa])
        db.commit()
        public_item = NoticeCandidate(
            title="关于 2026 年奖学金申请的通知",
            url="https://jwc.jlu.edu.cn/info/1.htm",
            publish_date=date(2026, 9, 10),
            content="公开正文",
        )
        oa_item = NoticeCandidate(
            title="关于 2026 年奖学金申请的通知",
            url="https://oa.jlu.edu.cn/notice?id=91",
            publish_date=date(2026, 9, 10),
            content="OA 转发正文",
            attachments=[
                {"filename": "申请表.docx", "url": "https://oa.jlu.edu.cn/download?id=9", "type": "docx"}
            ],
        )
        assert CrawlerManager._persist_candidate(db, public, public_item, False) == "NEW"
        assert CrawlerManager._persist_candidate(
            db, oa, oa_item, False, dedup_across_sources=True
        ) == "UNCHANGED"
        assert len(db.scalars(select(Notice)).all()) == 1
        assert len(db.scalars(select(NoticeSourceRelation)).all()) == 2
        attachment = db.scalar(select(Attachment))
        assert attachment is not None and attachment.filename == "申请表.docx"
