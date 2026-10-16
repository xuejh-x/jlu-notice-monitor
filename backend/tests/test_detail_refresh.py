"""Offline acceptance of detail-only revisions and source-owned attachments."""
from __future__ import annotations

from datetime import datetime, timedelta
import json

import httpx
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.config import Settings
import app.crawler.runner as runner
from app.crawler.runner import CrawlerManager, SourceRunResult
from app.database import Base
from app.database.session import engine as application_engine
from app.models import AppState, Attachment, Favorite, Notice, NoticeSourceRelation, NoticeUpdate, Source, UserState
from app.parsers import parse_detail_html
from app.schemas.notice import AttachmentData, NoticeCandidate
from app.services.detail_observation import load_observation, observation_key, relation_key
from app.services.retention import cleanup_notices
from app.sources.base import StaticHTMLSource
from app.sources.cloud import CloudFeedSource
from app.sources.generic import GenericPublicSource


NOW = datetime(2026, 10, 16, 1)


def file(name: str) -> AttachmentData:
    return AttachmentData(filename=name + ".pdf", url=f"https://test.invalid/{name}.pdf", type="pdf")


def candidate(index: int = 1, **changes) -> NoticeCandidate:
    return NoticeCandidate(title=f"独立测试通知 {index}", url=f"https://test.invalid/info/1/{index}.htm",
                           publish_date=NOW.date(), content="通知正文", attachments=[file("old")],
                           attachments_complete=True).model_copy(update=changes)


class FakeSource:
    list_contains_details = False

    def __init__(self, items):
        self.details = {item.url: item for item in items}
        self.calls = []
        self.fail = set()

    async def fetch_list(self):
        if self.list_contains_details:
            return list(self.details.values())
        return [item.model_copy(update={"content": "", "attachments": [], "attachments_complete": False})
                for item in self.details.values()]

    async def fetch_detail(self, item):
        self.calls.append(item.url)
        if item.url in self.fail:
            raise RuntimeError("FIXTURE_DETAIL_UNAVAILABLE")
        return self.details[item.url]

    async def close(self):
        pass


@pytest.fixture
def lab(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("No application DB connection or HTTP request allowed")

    event.listen(application_engine, "connect", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    clock = [NOW]
    settings = Settings(_env_file=None, database_url="sqlite://", deployment_role="standalone",
                        detail_recheck_delay_seconds=0)
    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    monkeypatch.setattr(runner, "utcnow", lambda: clock[0])
    # Match the production session factory, including disabled autoflush.
    with Session(engine, expire_on_commit=False, autoflush=False) as db:
        source = Source(code="offline-detail", name="独立来源", base_url="https://test.invalid")
        db.add(source)
        db.commit()
        yield db, source, CrawlerManager(tmp_path), clock, settings
    engine.dispose()
    event.remove(application_engine, "connect", forbidden)


async def run(lab, monkeypatch, adapter, *, bootstrap=False):
    db, source, manager, _, _ = lab
    monkeypatch.setattr(runner, "build_source", lambda _: adapter)
    result = SourceRunResult(source=source.code)
    await manager._execute_source_attempt(db, source, {"code": source.code}, bootstrap, result, "local")
    return result


def stored_files(db):
    return {item.url: (item.filename, item.type) for item in db.scalars(select(Attachment))}


def checkpoint(db, notice, source):
    relation = db.scalar(select(NoticeSourceRelation).where(NoticeSourceRelation.source_id == source.id))
    return load_observation(db, notice)["relations"][relation_key(source.id, relation.origin_item_key)]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["body", "add", "replace", "remove", "rename", "type", "body-and-attachment"])
async def test_unchanged_list_eventually_detects_detail_revisions_and_preserves_state(lab, monkeypatch, change):
    db, source, _, clock, _ = lab
    original = candidate(public_id="stable-public-id")
    adapter = FakeSource([original])
    first = await run(lab, monkeypatch, adapter, bootstrap=True)
    assert first.new_count == 0
    notice = db.scalar(select(Notice))
    user = db.scalar(select(UserState))
    user.is_read = user.is_favorite = True
    db.add(Favorite(notice_id=notice.id))
    db.commit()
    identity = (notice.id, notice.public_id, notice.canonical_url, notice.source_id, notice.first_seen_at)
    changes = {
        "body": {"content": "补充报名要求"},
        "add": {"attachments": [file("old"), file("new")]},
        "replace": {"attachments": [file("new")]},
        "remove": {"attachments": []},
        "rename": {"attachments": [file("old").model_copy(update={"filename": "更名.pdf"})]},
        "type": {"attachments": [file("old").model_copy(update={"type": "file"})]},
        "body-and-attachment": {"content": "补充报名要求", "attachments": [file("new")]},
    }[change]
    revised = original.model_copy(update=changes)
    adapter.details[original.url] = revised
    clock[0] += timedelta(hours=12)
    before_due = await run(lab, monkeypatch, adapter)
    assert before_due.detail_skipped == 1 and len(adapter.calls) == 1
    success_at = checkpoint(db, notice, source)["checked_at"]
    clock[0] += timedelta(hours=12)
    result = await run(lab, monkeypatch, adapter)
    assert result.updated_count == result.detail_fetched == 1 and result.detail_skipped == 0
    assert notice.content == revised.content
    assert stored_files(db) == {a.url: (a.filename, a.type) for a in revised.attachments}
    assert notice.version == 2 and len(db.scalars(select(NoticeUpdate)).all()) == 1
    assert checkpoint(db, notice, source)["checked_at"] != success_at
    assert identity == (notice.id, notice.public_id, notice.canonical_url, notice.source_id, notice.first_seen_at)
    assert notice.status == "baseline" and user.is_read and user.is_favorite
    assert db.scalar(select(Favorite)).notice_id == notice.id
    assert len(db.scalars(select(NoticeSourceRelation)).all()) == 1
    again = await run(lab, monkeypatch, adapter)
    assert again.detail_skipped == 1 and again.updated_count == 0 and notice.version == 2


@pytest.mark.asyncio
async def test_failed_detail_does_not_advance_success_or_mutate_snapshot_and_recovers(lab, monkeypatch):
    db, source, _, clock, _ = lab
    item = candidate()
    adapter = FakeSource([item])
    await run(lab, monkeypatch, adapter)
    notice = db.scalar(select(Notice))
    success = checkpoint(db, notice, source)["checked_at"]
    clock[0] += timedelta(days=1)
    adapter.fail.add(item.url)
    failed = await run(lab, monkeypatch, adapter)
    assert failed.status == "partial_failure" and item.url in failed.errors[0]
    assert checkpoint(db, notice, source)["checked_at"] == success
    assert checkpoint(db, notice, source)["attempted_at"] == clock[0].isoformat()
    assert notice.version == 1 and notice.content == item.content and file("old").url in stored_files(db)
    adapter.fail.clear()
    adapter.details[item.url] = item.model_copy(update={"content": "恢复后的新正文", "attachments": [file("new")]})
    recovered = await run(lab, monkeypatch, adapter)
    assert recovered.updated_count == 1 and notice.version == 2
    assert checkpoint(db, notice, source)["checked_at"] == clock[0].isoformat()
    assert set(stored_files(db)) == {file("new").url}


@pytest.mark.asyncio
async def test_bounded_rechecks_are_fair_even_when_first_details_fail(lab, monkeypatch):
    db, _, _, clock, settings = lab
    settings.detail_recheck_max_per_source = 2
    items = [candidate(index) for index in range(1, 7)]
    adapter = FakeSource(items)
    await run(lab, monkeypatch, adapter)
    clock[0] += timedelta(days=1)
    adapter.calls.clear()
    adapter.fail = {items[0].url, items[1].url}
    first = await run(lab, monkeypatch, adapter)
    assert len(adapter.calls) == 2 and first.detail_skipped == 4
    clock[0] += timedelta(minutes=1)
    adapter.calls.clear()
    second = await run(lab, monkeypatch, adapter)
    assert set(adapter.calls) == {items[2].url, items[3].url} and second.detail_skipped == 4
    clock[0] += timedelta(minutes=1)
    adapter.calls.clear()
    await run(lab, monkeypatch, adapter)
    assert set(adapter.calls) == {items[4].url, items[5].url}
    assert len(db.scalars(select(Notice)).all()) == 6


@pytest.mark.asyncio
async def test_legacy_rows_without_checkpoint_are_rechecked_with_budget(lab, monkeypatch):
    db, _, _, _, settings = lab
    settings.detail_recheck_max_per_source = 1
    adapter = FakeSource([candidate(1), candidate(2)])
    await run(lab, monkeypatch, adapter)
    for row in db.scalars(select(AppState).where(AppState.key.like("detail-observation:%"))):
        db.delete(row)
    db.commit()
    adapter.calls.clear()
    result = await run(lab, monkeypatch, adapter)
    assert len(adapter.calls) == 1 and result.detail_skipped == 1
    assert result.updated_count == 0 and result.unchanged_count == 2
    assert all(notice.version == 1 for notice in db.scalars(select(Notice)))


@pytest.mark.asyncio
async def test_inline_feed_changes_are_not_delayed_by_detail_interval(lab, monkeypatch):
    db, _, _, _, settings = lab
    settings.detail_recheck_max_per_source = 1
    adapter = FakeSource([candidate(1), candidate(2)])
    adapter.list_contains_details = True
    assert CloudFeedSource.list_contains_details is True
    await run(lab, monkeypatch, adapter)
    adapter.details = {url: item.model_copy(update={"content": "云端即时修订", "attachments": []})
                       for url, item in adapter.details.items()}
    result = await run(lab, monkeypatch, adapter)
    assert result.updated_count == 2 and result.detail_skipped == 0
    assert not stored_files(db) and all(n.version == 2 for n in db.scalars(select(Notice)))


def test_partial_snapshots_never_remove_and_complete_snapshots_remove_only_owned(lab):
    db, source, manager, _, _ = lab
    item = candidate()
    manager._persist_candidate(db, source, item, False)
    partial = item.model_copy(update={"attachments": [file("new")], "attachments_complete": False})
    assert manager._persist_candidate(db, source, partial, False) == "UPDATED"
    assert set(stored_files(db)) == {file("old").url, file("new").url}
    assert manager._persist_candidate(db, source, partial, False) == "UNCHANGED"
    assert manager._persist_candidate(db, source, item.model_copy(update={"attachments": []}), False) == "UPDATED"
    assert stored_files(db) == {}


def test_shared_attachments_and_other_sources_survive_removal(lab):
    db, source, manager, _, _ = lab
    item = candidate()
    manager._persist_candidate(db, source, item, False)
    other = Source(code="other", name="Other", base_url=source.base_url)
    db.add(other); db.commit()
    second = item.model_copy(update={"attachments": [file("old"), file("other")]})
    assert manager._persist_candidate(db, other, second, False, dedup_across_sources=True) == "UPDATED"
    notice = db.scalar(select(Notice))
    assert len(db.scalars(select(Notice)).all()) == 1 and notice.source_id == source.id
    assert manager._persist_candidate(db, source, item.model_copy(update={"attachments": []}), False) == "UPDATED"
    assert set(stored_files(db)) == {file("old").url, file("other").url}
    assert manager._persist_candidate(db, other, second.model_copy(update={"attachments": []}), False) == "UPDATED"
    assert stored_files(db) == {} and len(db.scalars(select(NoticeSourceRelation)).all()) == 2


def test_multiple_relations_of_same_source_keep_independent_ownership(lab):
    db, source, manager, _, _ = lab
    item = candidate(origin_item_key="origin:first")
    manager._persist_candidate(db, source, item, False)
    second = item.model_copy(update={"origin_item_key": "origin:second", "url": item.url + "?view=2", "attachments": [file("other")]})
    manager._persist_candidate(db, source, second, False, dedup_across_sources=True)
    assert len(db.scalars(select(Notice)).all()) == 1
    manager._persist_candidate(db, source, item.model_copy(update={"attachments": []}), False)
    assert set(stored_files(db)) == {file("other").url}


@pytest.mark.parametrize("corrupt", [False, True])
def test_legacy_or_corrupt_checkpoint_never_authorizes_attachment_deletion(lab, corrupt):
    db, source, manager, _, _ = lab
    item = candidate()
    manager._persist_candidate(db, source, item, False)
    notice = db.scalar(select(Notice))
    row = db.get(AppState, observation_key(notice.id))
    if corrupt:
        row.value = '{"schema":1,"relations":[]}'
    else:
        db.delete(row)
    db.commit()
    replacement = item.model_copy(update={"attachments": [file("new")]})
    assert manager._persist_candidate(db, source, replacement, False) == "UPDATED"
    assert set(stored_files(db)) == {file("old").url, file("new").url}
    manager._persist_candidate(db, source, item.model_copy(update={"attachments": []}), False)
    assert set(stored_files(db)) == {file("old").url}


def test_reordering_and_duplicate_references_do_not_create_revision(lab):
    db, source, manager, _, _ = lab
    item = candidate(attachments=[file("old"), file("new")])
    manager._persist_candidate(db, source, item, False)
    reordered = item.model_copy(update={"attachments": [file("new"), file("old"), file("old")]})
    assert manager._persist_candidate(db, source, reordered, False) == "UNCHANGED"
    assert db.scalar(select(Notice)).version == 1


def test_observation_and_attachment_revision_roll_back_atomically(lab):
    db, source, manager, clock, _ = lab
    item = candidate()
    manager._persist_candidate(db, source, item, False)
    notice = db.scalar(select(Notice))
    saved = db.get(AppState, observation_key(notice.id)).value
    clock[0] += timedelta(days=1)
    changed = item.model_copy(update={"attachments": [file("new")]})
    assert manager._persist_candidate(db, source, changed, False, commit=False) == "UPDATED"
    db.rollback()
    assert db.get(AppState, observation_key(notice.id)).value == saved
    assert notice.version == 1 and not db.scalars(select(NoticeUpdate)).all()
    assert set(stored_files(db)) == {file("old").url}


def test_retention_removes_checkpoint_in_same_transaction(lab):
    db, source, manager, clock, settings = lab
    manager._persist_candidate(db, source, candidate(), False)
    notice_id = db.scalar(select(Notice.id))
    clock[0] += timedelta(days=366)
    cleanup_notices(db, settings, now=clock[0]); db.commit()
    assert db.get(Notice, notice_id) is None and db.get(AppState, observation_key(notice_id)) is None


def test_internal_evidence_flag_does_not_change_attachment_dto():
    assert "attachments_complete" not in candidate().model_dump()
    assert set(candidate().model_dump()["attachments"][0]) == {"filename", "url", "type"}


@pytest.mark.parametrize("scope,dynamic,expected", [
    ('<form name="_newscontent_fromname">{body}</form>', "", True),
    ('<article class="type-post">{body}</article>', "", True),
    ('<div>{body}</div>', "", False),
    ('<form name="_newscontent_fromname">{body}</form>', '<script>loadFiles()</script>', False),
    ('<form name="_newscontent_fromname">{body}</form>', '<iframe src="/files"></iframe>', False),
    ('<form name="_newscontent_fromname">{body}</form>', '<a download href="/unknown.xyz">附件</a>', False),
    ('<form name="_newscontent_fromname">{body}</form>', '<a href="/not-extracted.rar">旧式文件.rar</a>', False),
    ('<form name="_newscontent_fromname">{body}</form><aside><a href="/outside.pdf">附件.pdf</a></aside>', "", False),
    ('<form name="_newscontent_fromname">{body}</form>', '<a href="https://[broken">畸形链接</a>', False),
])
def test_only_recognized_static_attachment_scope_is_complete(scope, dynamic, expected):
    body = '<div class="v_news_content">通知正文<a href="/old.pdf">old.pdf</a>' + dynamic + '</div>'
    parsed = parse_detail_html(scope.format(body=body), candidate().url, candidate())
    assert parsed.attachments_complete is expected and parsed.attachments[0].url == file("old").url


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", [StaticHTMLSource, GenericPublicSource])
async def test_url_rejection_downgrades_complete_snapshot(lab, monkeypatch, adapter_type):
    from app.services.source_security import UnsafeSourceUrl
    import app.sources.base as base
    html = '<form name="_newscontent_fromname"><div class="v_news_content">通知正文<a href="/old.pdf">old.pdf</a></div></form>'
    config = {"code": "offline", "name": "Offline", "base_url": "https://test.invalid"}
    adapter = adapter_type(config)
    async def reject(*args, **kwargs):
        raise UnsafeSourceUrl("FIXTURE_BLOCKED")
    async def get_static(url):
        return html
    async def get_generic(url):
        return html, "text/html", url
    if adapter_type is StaticHTMLSource:
        monkeypatch.setattr(adapter, "_get", get_static)
        monkeypatch.setattr(base, "validate_local_source_url", reject)
    else:
        monkeypatch.setattr(adapter.fetcher, "get", get_generic)
        monkeypatch.setattr(adapter.fetcher, "validate_url", reject)
    try:
        detail = await adapter.fetch_detail(candidate(content=""))
        assert detail.attachments == [] and not detail.attachments_complete
    finally:
        await adapter.close()


def test_attachment_only_revision_keeps_enriched_metadata(lab):
    db, source, manager, _, _ = lab
    item = candidate(publisher="已验证来源", target_students="全体学生")
    manager._persist_candidate(db, source, item, False)
    update = item.model_copy(update={"publisher": None, "target_students": None, "attachments": [file("new")]})
    assert manager._persist_candidate(db, source, update, False) == "UPDATED"
    notice = db.scalar(select(Notice))
    assert notice.publisher == item.publisher and notice.target_students == item.target_students
    revision = db.scalar(select(NoticeUpdate))
    assert revision.old_hash != revision.new_hash and "附件引用" in revision.summary


def test_same_relation_origin_key_transition_keeps_ownership(lab):
    db, source, manager, _, _ = lab
    item = candidate(origin_item_key="local-origin")
    manager._persist_candidate(db, source, item, False)
    notice = db.scalar(select(Notice))
    # Cache the collection as a real session may do before an update.
    assert [a.url for a in notice.attachments] == [file("old").url]
    switched = item.model_copy(update={"origin_item_key": "cloud-origin", "attachments": [file("new")]})
    assert manager._persist_candidate(db, source, switched, False) == "UPDATED"
    assert [a.url for a in notice.attachments] == [file("new").url]
    assert len(load_observation(db, notice)["relations"]) == 1
    assert len(db.scalars(select(NoticeSourceRelation)).all()) == 1


@pytest.mark.asyncio
async def test_origin_transition_is_verified_before_skipping_recent_detail(lab, monkeypatch):
    db, _, _, _, _ = lab
    item = candidate(origin_item_key="legacy-local")
    adapter = FakeSource([item])
    await run(lab, monkeypatch, adapter)
    adapter.details[item.url] = item.model_copy(update={"origin_item_key": "new-feed", "attachments": []})
    result = await run(lab, monkeypatch, adapter)
    assert result.detail_fetched == 1 and result.updated_count == 1
    notice = db.scalar(select(Notice))
    assert stored_files(db) == {} and len(load_observation(db, notice)["relations"]) == 1


@pytest.mark.asyncio
async def test_real_cloud_feed_parser_detects_attachment_only_change_without_school_requests(lab, monkeypatch):
    db, source, _, _, _ = lab
    payload = {"version": "1", "items": [{
        "public_id": "feed-public-id", "origin_item_key": "feed-origin", "title": "Feed notice",
        "url": candidate().url, "content": "Feed body", "attachments": [file("old").model_dump()],
    }]}
    adapter = CloudFeedSource({"code": source.code, "name": source.name, "base_url": source.base_url,
                               "public_feed_url": "https://feed.invalid/"})
    async def get(url, **kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(adapter.client, "get", get)
    monkeypatch.setattr(adapter, "_load_cursor", lambda: (None, 0))
    monkeypatch.setattr(adapter, "_has_baseline", lambda: True)
    first = await run(lab, monkeypatch, adapter)
    assert first.new_count == 1
    notice = db.scalar(select(Notice))
    payload["items"][0]["attachments"] = []
    updated = await run(lab, monkeypatch, adapter)
    assert updated.updated_count == 1 and updated.detail_skipped == 0
    assert notice.version == 2 and stored_files(db) == {}


def test_attachment_revision_advances_public_feed_without_client_state_in_cloud(lab):
    from app.api.public_feed import public_notices
    db, source, manager, clock, settings = lab
    settings.deployment_role = "cloud"
    item = candidate()
    manager._persist_candidate(db, source, item, False)
    notice = db.scalar(select(Notice))
    before = notice.updated_at
    clock[0] += timedelta(seconds=1)
    manager._persist_candidate(db, source, item.model_copy(update={"attachments": []}), False)
    response = public_notices(source=source.code, updated_after=before, after_id=0, page_size=100, db=db)
    assert len(response["items"]) == 1 and response["items"][0]["attachments"] == []
    assert response["items"][0]["updated_at"] > before
    assert db.scalars(select(UserState)).all() == [] and db.scalars(select(Favorite)).all() == []


@pytest.mark.asyncio
async def test_periodic_rechecks_obey_delay_and_source_time_limit(lab, monkeypatch):
    _, _, _, clock, settings = lab
    adapter = FakeSource([candidate()])
    await run(lab, monkeypatch, adapter)
    clock[0] += timedelta(days=1)
    settings.detail_recheck_delay_seconds = 1.0
    ticks = [0.0]
    delays = []
    monkeypatch.setattr(runner.time, "perf_counter", lambda: ticks[0])
    async def sleep(seconds):
        delays.append(seconds)
        ticks[0] = float(settings.source_run_timeout_seconds)
    monkeypatch.setattr(runner.asyncio, "sleep", sleep)
    result = await run(lab, monkeypatch, adapter)
    assert delays == [1.0] and len(adapter.calls) == 1
    assert result.errors == ["SOURCE_RUN_TIME_LIMIT"] and result.detail_fetched == 0


def test_no_checkpoint_is_inherited_by_reused_notice_id(lab):
    db, source, manager, clock, _ = lab
    manager._persist_candidate(db, source, candidate(), False)
    old = db.scalar(select(Notice))
    old_id = old.id
    db.delete(old); db.commit()
    # Deliberately leave its AppState row, simulating deletion outside retention.
    assert db.get(AppState, observation_key(old_id)) is not None
    clock[0] += timedelta(seconds=1)
    manager._persist_candidate(db, source, candidate(2, attachments=[]), False)
    new = db.scalar(select(Notice))
    assert new.id == old_id and new.version == 1 and stored_files(db) == {}
    assert load_observation(db, new)["identity"][0] == clock[0].isoformat()


def test_writing_observation_reloads_cached_state_from_another_session(lab):
    db, source, manager, _, _ = lab
    manager._persist_candidate(db, source, candidate(), False)
    notice = db.scalar(select(Notice))
    cached = db.get(AppState, observation_key(notice.id))
    value = json.loads(cached.value)
    value["legacy"][file("manual").url] = {"filename": "manual.pdf", "type": "pdf"}
    with Session(db.get_bind()) as other:
        row = other.get(AppState, cached.key)
        row.value = json.dumps(value)
        other.commit()
    assert file("manual").url not in load_observation(db, notice)["legacy"]
    assert file("manual").url in load_observation(db, notice, for_update=True)["legacy"]
