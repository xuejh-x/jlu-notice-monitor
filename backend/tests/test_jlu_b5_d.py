"""Attachment evidence conflicts and isolated execution-policy acceptance."""
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
import app.crawler.runner as runner
from app.crawler.runner import CLOUD_FALLBACK_REASONS, CrawlerManager
from app.database import Base
from app.models import AppState, Notice, Source, UserState
from app.schemas.notice import NoticeCandidate
from app.services.attachment_validation import classify_attachment_prefix
from app.sources.base import SourceError


@pytest.mark.parametrize("mime,prefix,kind", [
    ("image/jpeg", b"%PDF-1.7 test", "pdf"),
    ("application/pdf", b"PK\x03\x04test", "docx"),
    ("text/plain", b"%PDF-1.7 test", "pdf"),
    ("application/vnd.ms-excel", b"%PDF-1.7 test", "pdf"),
])
def test_known_mime_body_conflicts_never_verify_a_file(mime, prefix, kind):
    result = classify_attachment_prefix(200, {"Content-Type": mime}, prefix, kind)
    assert result["category"] == "HEADER_BODY_MISMATCH" and not result["file_prefix_verified"]


def test_container_signature_does_not_override_a_conflicting_specific_office_mime():
    result = classify_attachment_prefix(200, {"Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, b"PK\x03\x04test", "xlsx")
    assert result["category"] == "FILE_TYPE_MISMATCH" and not result["file_prefix_verified"]


@pytest.mark.parametrize("content_range", ["bytes 10-99/100", "bytes 0-200/100", "garbage", "bytes 0-2/100"])
def test_invalid_or_nonzero_range_does_not_prove_the_file_prefix(content_range):
    result = classify_attachment_prefix(206, {"Content-Type": "application/pdf", "Content-Range": content_range}, b"%PDF-1.7", "pdf")
    assert result["category"] == "RANGE_RESPONSE_MISMATCH" and not result["file_prefix_verified"]


@pytest.mark.parametrize("mime,signature,kind", [
    ("application/pdf", b"%PDF-1.7", "pdf"),
    ("application/octet-stream", b"PK\x03\x04test", "docx"),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04test", "xlsx"),
])
def test_consistent_bounded_prefix_remains_only_prefix_evidence(mime, signature, kind):
    result = classify_attachment_prefix(206, {"content-type": mime, "content-range": "bytes 0-4095/10000"}, signature, kind)
    assert result["file_prefix_verified"] and result["complete_download_verified"] is False


class ControlledAdapter:
    def __init__(self, error=None):
        self.error = error
    async def fetch_list(self):
        if self.error:
            raise SourceError(self.error)
        return [NoticeCandidate(title="隔离来源执行验证", url="https://fixture.test/info/1/1.htm", publish_date=date.today())]
    async def fetch_detail(self, item):
        return item.model_copy(update={"content": "有效测试正文"})
    async def close(self):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", CLOUD_FALLBACK_REASONS)
async def test_desktop_cloud_preferred_fallback_keeps_one_baseline_and_user_state(reason, tmp_path, monkeypatch):
    settings = Settings(_env_file=None, deployment_role="desktop", app_data_dir=str(tmp_path))
    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    calls = []
    def build(config):
        calls.append(config["parser"])
        return ControlledAdapter(reason if config["parser"] == "cloud_feed" else None)
    monkeypatch.setattr(runner, "build_source", build)
    with Session(engine, expire_on_commit=False) as db:
        source = Source(code="fixture", name="Fixture", base_url="https://fixture.test", ownership="OFFICIAL_CLOUD", execution_policy="cloud_preferred")
        db.add(source)
        db.commit()
        monkeypatch.setattr(runner, "SessionLocal", lambda: db)
        config = {"code": "fixture", "name": "Fixture", "base_url": source.base_url, "ownership": "OFFICIAL_CLOUD",
                  "execution_policy": "cloud_preferred", "parser": "cloud_feed", "fallback_parser": "generic_html"}
        manager = CrawlerManager(tmp_path)
        first = await manager._run_source(config, False)
        assert first.status == "success" and first.fallback_reason == reason and first.new_count == 0
        notice = db.scalar(select(Notice))
        state = db.scalar(select(UserState))
        state.is_favorite = True
        db.commit()
        snapshot = notice.id, notice.status, notice.version, state.is_read, state.is_favorite, state.updated_at
        second = await manager._run_source(config, False)
        assert second.status == "success" and second.new_count == second.updated_count == 0 and second.detail_skipped == 1
        notice = db.scalar(select(Notice))
        state = db.scalar(select(UserState))
        assert (notice.id, notice.status, notice.version, state.is_read, state.is_favorite, state.updated_at) == snapshot
        assert calls == ["cloud_feed", "generic_html"] * 2
        assert len(db.scalars(select(AppState).where(AppState.key.startswith("local-fallback-baseline:"))).all()) == 1
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("role,ownership,policy,parser", [
    ("desktop", "SHARED_CLOUD", "cloud_only", "cloud_feed"),
    ("desktop", "OFFICIAL_CLOUD", "cloud_only", "cloud_feed"),
    ("cloud", "OFFICIAL_CLOUD", "cloud_preferred", "generic_html"),
    ("desktop", "CUSTOM_LOCAL_PRIVATE", "local_only", "generic_html"),
])
async def test_execution_boundaries_do_not_create_an_unauthorized_fallback(role, ownership, policy, parser, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "get_settings", lambda: Settings(_env_file=None, deployment_role=role, app_data_dir=str(tmp_path)))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    calls = []
    def build(config):
        calls.append(config["parser"])
        return ControlledAdapter("PUBLIC_FEED_NOT_CONFIGURED")
    monkeypatch.setattr(runner, "build_source", build)
    with Session(engine, expire_on_commit=False) as db:
        source = Source(code="fixture", name="Fixture", base_url="https://fixture.test", ownership=ownership, execution_policy=policy)
        db.add(source)
        db.commit()
        monkeypatch.setattr(runner, "SessionLocal", lambda: db)
        result = await CrawlerManager(tmp_path)._run_source({"code": "fixture", "name": "Fixture", "base_url": source.base_url,
            "ownership": ownership, "execution_policy": policy, "parser": parser, "fallback_parser": "generic_html"}, False)
        assert result.status == "failure" and not result.fallback_used and calls == [parser]
        assert not db.scalars(select(AppState)).all() and not db.scalars(select(Notice)).all()
    engine.dispose()
