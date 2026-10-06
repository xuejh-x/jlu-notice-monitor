from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.crawler.runner as runner_module
from app.config import Settings
from app.crawler.runner import CrawlerManager, SourceRunResult
from app.database import Base
from app.models import AppState, Notice, NotificationEvent, Source, UserState
from app.parsers.html import parse_list_html
from app.schemas.notice import NoticeCandidate
from app.services.retention import cleanup_notices, notice_is_expired


NOW = datetime(2026, 10, 6, 11)
CUTOFF = (NOW - timedelta(days=365)).date()


@pytest.fixture
def isolated_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = Settings(_env_file=None, deployment_role="desktop")
    monkeypatch.setattr(runner_module, "get_settings", lambda: settings)
    monkeypatch.setattr(runner_module, "utcnow", lambda: NOW)
    with Session(engine) as db:
        source = Source(code="fixture", name="Fixture", base_url="https://example.test")
        db.add(source)
        db.flush()
        db.add(AppState(key=f"local-fallback-baseline:{source.id}", value="established"))
        db.commit()
        yield db, source
    engine.dispose()


class Adapter:
    def __init__(self, items, details=None):
        self.items = items
        self.details = details or {}
        self.calls = []

    async def fetch_list(self):
        return self.items

    async def fetch_detail(self, item):
        self.calls.append(item.url)
        return self.details.get(item.url, item)

    async def close(self):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("execution", ["local", "cloud"])
@pytest.mark.parametrize("bootstrap", [False, True])
async def test_old_list_item_never_fetches_detail_or_enters_database(
    isolated_db, monkeypatch, tmp_path, execution, bootstrap
):
    db, source = isolated_db
    old = NoticeCandidate(title="Expired", url="https://example.test/old", publish_date=CUTOFF - timedelta(days=1))
    boundary = NoticeCandidate(title="Boundary", url="https://example.test/boundary", publish_date=CUTOFF)
    recent = NoticeCandidate(title="Recent", url="https://example.test/new", publish_date=NOW.date())
    adapter = Adapter([old, boundary, recent])
    monkeypatch.setattr(runner_module, "build_source", lambda _: adapter)
    manager = CrawlerManager(cache_dir=tmp_path)
    result = SourceRunResult(source=source.code)
    assert await manager._execute_source_attempt(db, source, {}, bootstrap, result, execution)
    db.commit()
    assert adapter.calls == [boundary.url, recent.url]
    assert {n.url for n in db.scalars(select(Notice))} == {boundary.url, recent.url}
    assert result.new_count == (0 if bootstrap else 2)
    assert all(s.is_read == bootstrap for s in db.scalars(select(UserState)))


@pytest.mark.asyncio
async def test_date_discovered_in_detail_is_filtered_but_unknown_date_is_kept(
    isolated_db, monkeypatch, tmp_path
):
    db, source = isolated_db
    old = NoticeCandidate(title="Undated list", url="https://example.test/old")
    unknown = NoticeCandidate(title="Unknown date", url="https://example.test/unknown")
    adapter = Adapter([old, unknown], {old.url: old.model_copy(update={"publish_date": CUTOFF - timedelta(days=1)})})
    monkeypatch.setattr(runner_module, "build_source", lambda _: adapter)
    result = SourceRunResult(source=source.code)
    await CrawlerManager(cache_dir=tmp_path)._execute_source_attempt(db, source, {}, False, result, "local")
    db.commit()
    assert result.new_count == 1
    assert [n.url for n in db.scalars(select(Notice))] == [unknown.url]
    assert len(db.scalars(select(UserState)).all()) == 1


def test_cleanup_then_reimport_cannot_recreate_new_unread(isolated_db):
    db, source = isolated_db
    candidate = NoticeCandidate(title="Repeated old notice", url="https://example.test/repeated", publish_date=CUTOFF - timedelta(days=1))
    notice = Notice(title=candidate.title, normalized_title=candidate.title, url=candidate.url, canonical_url=candidate.url,
                    source_id=source.id, publish_date=candidate.publish_date, content_hash="old")
    db.add(notice)
    db.flush()
    db.add(UserState(notice_id=notice.id, is_read=False, is_favorite=True))
    db.commit()
    for _ in range(2):
        cleanup_notices(db, Settings(_env_file=None, deployment_role="desktop"), now=NOW)
        db.commit()
        assert CrawlerManager._has_local_fallback_baseline(db, source)
        assert CrawlerManager._persist_candidate(db, source, candidate, bootstrap=False) == "SKIPPED"
        db.commit()
        assert db.scalars(select(Notice)).all() == []
        assert db.scalars(select(UserState)).all() == []
        assert db.scalars(select(NotificationEvent)).all() == []


def test_retention_boundary_and_unknown_publication_date(isolated_db):
    db, source = isolated_db
    settings = Settings(_env_file=None, deployment_role="desktop")
    assert notice_is_expired(CUTOFF - timedelta(days=1), settings, now=NOW)
    assert not notice_is_expired(CUTOFF, settings, now=NOW)
    assert not notice_is_expired(None, settings, now=NOW)
    for index, published in enumerate([CUTOFF, None]):
        n = Notice(title=str(index), normalized_title=str(index), url=f"https://example.test/{index}",
                   canonical_url=f"https://example.test/{index}", source_id=source.id,
                   content_hash="x", publish_date=published, first_seen_at=NOW - timedelta(days=730))
        db.add(n)
    db.commit()
    assert cleanup_notices(db, settings, now=NOW).deleted_count == 0
    assert len(db.scalars(select(Notice)).all()) == 2


def test_list_date_next_to_nested_title_uses_same_notice_row():
    html = '''<ul><li><span class="time">2024-05-06</span><div class="title"><a href="/info/1.htm">Old</a></div></li>
    <li><span class="time">2026-10-06</span><div class="title"><a href="/info/2.htm">New</a></div></li></ul>'''
    items = parse_list_html(html, "https://example.test/list.htm")
    assert [i.publish_date.isoformat() for i in items] == ["2024-05-06", "2026-10-06"]
