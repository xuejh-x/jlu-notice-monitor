from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.crawler.runner as runner_module
from app.crawler.runner import CrawlerManager
from app.database import Base, get_db
from app.main import app
from app.models import AppState, Notice, NotificationEvent, NotificationPreference, Source, UserState
from app.services.page_monitor import baseline_key
from app.sources.base import SourceError
from app.sources.lqb import LanqiaoSource, normalize_text
from app.sources.registry import build_source

URL = "https://lus-jlu.github.io/lqb.html"
CONFIG = {"code": "lqb", "name": "蓝桥杯赛事信息（吉林大学）", "base_url": URL,
          "parser": "lqb", "ownership": "CUSTOM_LOCAL_PUBLIC", "execution_policy": "local_only"}
HTML = """<html><body><div class="markdown-body">
<h1>蓝桥杯全国大学生软件和信息技术大赛</h1>
<h2>第18届蓝桥杯大赛的比赛科目（随时更新）</h2>
<ul><li>软件赛：Python程序设计</li><li>电子赛：嵌入式设计</li></ul>
<h2>第18届蓝桥杯大赛的参赛日程（随时更新）</h2>
<ul><li>软件赛<ul><li>报名时间：2026年10月8日至2026年12月18日</li>
<li>省赛时间：2027年4月10日</li><li>国赛时间：待定</li></ul></li></ul>
<hr><h1>蓝桥杯大赛@吉林大学</h1>
<h2>〖组织管理〗</h2><ul><li>负责单位：软件学院</li><li>参赛群：测试群</li></ul>
<h2>〖院校报名〗</h2><ol><li>学生认证</li><li>报名后院校审核与缴费</li></ol>
<h2>〖权威认可〗</h2><p>蓝桥杯竞赛获奖可申请奖励。</p>
<table><tr><th>竞赛名称</th><th>一等奖</th></tr><tr><td>ICPC</td><td>10000元</td></tr>
<tr><td>蓝桥杯</td><td>5000元</td></tr></table>
<h2>〖鼓励措施〗</h2><div><p>第18届参赛选手可申请报名费资助600元。</p></div>
<hr><h1>截至目前，吉林大学累计获得100项奖项</h1>
<h2>第18届蓝桥杯报名人数28人</h2><ul><li>报名统计</li></ul>
<h2>第17届蓝桥杯获奖名单</h2><ul><li>历史获奖学生甲</li></ul>
</div></body></html>"""


@pytest.fixture
def monitor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        source = Source(**{key: CONFIG[key] for key in ("code", "name", "base_url", "parser", "ownership", "execution_policy")},
                        source_type="single_page_monitor", execution="local", source_scope="personal")
        db.add(source)
        db.add(NotificationPreference(id=1, enabled=True))
        db.commit()
        source_id = source.id
    page = {"html": HTML, "status": 200, "failure": False}

    def response(request: httpx.Request) -> httpx.Response:
        if page["failure"]:
            raise httpx.ConnectError("test network unavailable", request=request)
        return httpx.Response(int(page["status"]), text=str(page["html"]), request=request)

    def adapter(config):
        result = LanqiaoSource(config)
        result.retries = 0
        result.client = httpx.AsyncClient(transport=httpx.MockTransport(response))
        return result

    monkeypatch.setattr(runner_module, "SessionLocal", sessions)
    monkeypatch.setattr(runner_module, "build_source", adapter)
    manager = CrawlerManager(cache_dir=tmp_path)
    yield manager, sessions, source_id, page, engine
    engine.dispose()


def counts(db: Session) -> tuple[int, int, int]:
    return tuple(db.scalar(select(func.count()).select_from(model)) or 0
                 for model in (Notice, UserState, NotificationEvent))


@pytest.mark.asyncio
async def test_first_fetch_and_repeat_establish_silent_baseline(monitor):
    manager, sessions, sid, _, _ = monitor
    for _ in range(2):
        result = await manager._run_source(CONFIG, False)
        assert result.status == "success" and result.new_count == 0
        assert result.detail_fetched == 0
    with sessions() as db:
        assert counts(db) == (0, 0, 0)
        state = json.loads(db.get(AppState, baseline_key(sid)).value)
        assert state["revision"] == 0 and len(state["hashes"]) == 6
        assert "历史获奖学生甲" not in json.dumps(state, ensure_ascii=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(("before", "after", "section"), [
    ("Python程序设计", "Python程序设计、Java软件开发", "比赛科目"),
    ("2026年12月18日", "2026年12月19日", "参赛日程"),
    ("国赛时间：待定", "国赛时间：暂定2027年6月12日", "参赛日程"),
    ("参赛群：测试群", "参赛群：新测试群", "组织管理"),
    ("院校审核与缴费", "院校审核与线上缴费", "院校报名"),
    ("5000元", "6000元", "参赛相关政策"),
    ("资助600元", "资助700元", "鼓励措施"),
])
async def test_important_changes_create_unread_diff(monitor, before, after, section):
    manager, sessions, _, page, _ = monitor
    await manager._run_source(CONFIG, False)
    page["html"] = HTML.replace(before, after)
    result = await manager._run_source(CONFIG, False)
    assert result.new_count == 1 and result.status == "success"
    assert (await manager._run_source(CONFIG, False)).new_count == 0
    with sessions() as db:
        assert counts(db) == (1, 1, 1)
        notice = db.scalar(select(Notice))
        assert not notice.user_state.is_read
        assert notice.publish_date is None and notice.first_seen_at is not None
        assert notice.url == URL and notice.source_relations[0].source_url == URL
        assert normalize_text(before) in notice.content and normalize_text(after) in notice.content and section in notice.content
        assert notice.category != "other"
        assert notice.registration_deadline is None  # diff's removed dates are not current deadlines


@pytest.mark.asyncio
@pytest.mark.parametrize(("before", "after"), [
    ("历史获奖学生甲", "历史获奖学生乙"), ("28人", "29人"), ("100项", "101项"),
    ("10000元", "12000元"), ("<body>", "<body><style>body{color:red}</style>"),
    ("Python程序设计", "<strong>Python程序设计</strong>"),
    ("Python程序设计", "Python<strong>程序设计</strong>"),
    ("600元。", "600元"),
    ("软件学院", "软件 学院"),
])
async def test_irrelevant_or_editorial_changes_do_not_notify(monitor, before, after):
    manager, sessions, _, page, _ = monitor
    await manager._run_source(CONFIG, False)
    page["html"] = HTML.replace(before, after)
    assert (await manager._run_source(CONFIG, False)).new_count == 0
    with sessions() as db:
        assert counts(db) == (0, 0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["network", "http", "empty", "structure", "edition", "section"])
async def test_failed_fetch_preserves_baseline_then_recovers(monitor, failure):
    manager, sessions, sid, page, _ = monitor
    await manager._run_source(CONFIG, False)
    with sessions() as db:
        original = db.get(AppState, baseline_key(sid)).value
    if failure == "network":
        page["failure"] = True
    elif failure == "http":
        page["status"] = 404
    else:
        page["html"] = {"empty": "", "structure": "<h1>Maintenance</h1>",
                        "edition": HTML.replace("第18届蓝桥杯大赛的参赛日程", "第19届蓝桥杯大赛的参赛日程"),
                        "section": HTML.replace("<li>负责单位：软件学院</li><li>参赛群：测试群</li>", "")}[failure]
    assert (await manager._run_source(CONFIG, False)).status == "failure"
    with sessions() as db:
        assert db.get(AppState, baseline_key(sid)).value == original
        assert counts(db)[:2] == (0, 0)
    page.update(html=HTML.replace("资助600元", "资助700元"), status=200, failure=False)
    assert (await manager._run_source(CONFIG, False)).new_count == 1


@pytest.mark.asyncio
async def test_initial_failure_does_not_establish_baseline(monitor):
    manager, sessions, sid, page, _ = monitor
    page["status"] = 500
    assert (await manager._run_source(CONFIG, False)).status == "failure"
    with sessions() as db:
        assert db.get(AppState, baseline_key(sid)) is None
    page["status"] = 200
    assert (await manager._run_source(CONFIG, False)).new_count == 0


@pytest.mark.asyncio
async def test_baseline_write_failure_rolls_back_notice_and_event(monitor):
    manager, sessions, sid, page, engine = monitor
    await manager._run_source(CONFIG, False)
    with sessions() as db:
        original = db.get(AppState, baseline_key(sid)).value
    page["html"] = HTML.replace("资助600元", "资助700元")

    def reject_state_update(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE app_state"):
            raise RuntimeError("simulated baseline storage failure")

    event.listen(engine, "before_cursor_execute", reject_state_update)
    try:
        assert (await manager._run_source(CONFIG, False)).status == "failure"
    finally:
        event.remove(engine, "before_cursor_execute", reject_state_update)
    with sessions() as db:
        assert db.get(AppState, baseline_key(sid)).value == original
        assert counts(db)[:2] == (0, 0)
        assert db.scalar(select(func.count()).select_from(NotificationEvent).where(NotificationEvent.notice_id.is_not(None))) == 0
    assert (await manager._run_source(CONFIG, False)).new_count == 1
    assert (await manager._run_source(CONFIG, False)).new_count == 0


@pytest.mark.asyncio
async def test_revisions_same_url_reversion_and_read_state_are_independent(monitor):
    manager, sessions, _, page, _ = monitor
    await manager._run_source(CONFIG, False)
    for fee in (700, 800, 600):
        page["html"] = HTML.replace("资助600元", f"资助{fee}元")
        # Each _run_source builds a fresh adapter; no process-local baseline.
        assert (await manager._run_source(CONFIG, False)).new_count == 1
        assert (await manager._run_source(CONFIG, False)).new_count == 0
        with sessions() as db:
            notice = db.scalar(select(Notice).order_by(Notice.id.desc()))
            notice.user_state.is_read = True
            db.commit()
    with sessions() as db:
        assert counts(db) == (3, 3, 3)
        assert len(set(db.scalars(select(Notice.public_id)))) == 3
        assert all(row.is_read for row in db.scalars(select(UserState)))


@pytest.mark.asyncio
async def test_new_edition_is_an_update_not_a_new_baseline(monitor):
    manager, _, _, page, _ = monitor
    await manager._run_source(CONFIG, False)
    page["html"] = HTML.replace("第18届", "第19届")
    assert (await manager._run_source(CONFIG, False)).new_count == 1


@pytest.mark.asyncio
async def test_corrupt_baseline_is_not_reset(monitor):
    manager, sessions, sid, _, _ = monitor
    with sessions() as db:
        db.add(AppState(key=baseline_key(sid), value="not-json"))
        db.commit()
    assert (await manager._run_source(CONFIG, False)).status == "failure"
    with sessions() as db:
        assert db.get(AppState, baseline_key(sid)).value == "not-json"


@pytest.mark.asyncio
async def test_source_filter_detail_read_all_and_management_guards(monitor):
    manager, sessions, _, page, _ = monitor
    await manager._run_source(CONFIG, False)
    page["html"] = HTML.replace("资助600元", "资助700元")
    await manager._run_source(CONFIG, False)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        listing = client.get("/api/notices?source=lqb&read=false").json()
        assert listing["total"] == 1 and listing["unread_count"] == 1
        item = listing["items"][0]
        assert item["sources"][0]["code"] == "lqb" and item["publish_date"] is None
        assert client.get(f"/api/notices/{item['id']}").json()["url"] == URL
        assert client.post(f"/api/notices/{item['id']}/read").status_code == 200
        assert client.get("/api/notices?source=lqb&read=false").json()["total"] == 0
        client.post(f"/api/notices/{item['id']}/unread")
        assert client.post("/api/notices/read-all").json() == {"updated": 1}
        assert client.post("/api/notices/read-all").json() == {"updated": 0}
        source = client.get("/api/source-config").json()[0]
        assert client.patch(f"/api/source-config/{source['id']}", json={"name": "changed"}).status_code == 409
        assert client.post(f"/api/source-config/{source['id']}/promote", json={"admin_key": "test"}).status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_registered_adapter_and_parser_rejects_missing_core_sections():
    adapter = build_source(CONFIG)
    assert isinstance(adapter, LanqiaoSource)
    with pytest.raises(SourceError, match="PARSER_FAILED"):
        adapter.parse_snapshot(HTML.replace("〖院校报名〗", "Changed template"))


@pytest.mark.asyncio
async def test_baseline_is_source_scoped_and_existing_user_state_is_preserved(monitor):
    manager, sessions, sid, page, _ = monitor
    second_config = {**CONFIG, "code": "lqb-second", "base_url": "https://example.test/lqb.html"}
    with sessions() as db:
        other = Source(code="other", name="Existing source", base_url="https://example.test")
        second = Source(code="lqb-second", name="Second monitor", base_url=second_config["base_url"],
                        ownership="CUSTOM_LOCAL_PUBLIC", parser="lqb", execution_policy="local_only")
        db.add_all([other, second])
        db.flush()
        notice = Notice(title="Existing unread", normalized_title="existing", url="https://example.test/old",
                        canonical_url="https://example.test/old", source_id=other.id, content_hash="a" * 64)
        notice.user_state = UserState(is_read=False, is_favorite=True)
        db.add(notice)
        db.commit()
        old_id, second_id = notice.id, second.id
    await manager._run_source(CONFIG, False)
    page["html"] = HTML.replace("资助600元", "资助700元")
    assert (await manager._run_source(second_config, False)).new_count == 0
    assert (await manager._run_source(CONFIG, False)).new_count == 1
    with sessions() as db:
        assert db.get(AppState, baseline_key(sid)) is not None
        assert db.get(AppState, baseline_key(second_id)) is not None
        old = db.get(Notice, old_id)
        assert not old.user_state.is_read and old.user_state.is_favorite
        assert old.title == "Existing unread"


@pytest.mark.asyncio
async def test_multiple_section_changes_emit_one_notice_and_link_changes_are_detected(monitor):
    manager, sessions, _, page, _ = monitor
    page["html"] = HTML.replace("学生认证", '<a href="https://example.test/signup">学生认证</a>')
    await manager._run_source(CONFIG, False)
    page["html"] = str(page["html"]).replace("https://example.test/signup", "https://example.test/new-signup").replace("资助600元", "资助700元")
    assert (await manager._run_source(CONFIG, False)).new_count == 1
    with sessions() as db:
        notice = db.scalar(select(Notice))
        assert counts(db) == (1, 1, 1)
        assert "院校报名" in notice.content and "鼓励措施" in notice.content
        assert "https://example.test/new-signup" in notice.content


@pytest.mark.asyncio
async def test_subject_reordering_is_ignored_but_registration_step_order_matters(monitor):
    manager, _, _, page, _ = monitor
    await manager._run_source(CONFIG, False)
    page["html"] = HTML.replace("<li>软件赛：Python程序设计</li><li>电子赛：嵌入式设计</li>",
                               "<li>电子赛：嵌入式设计</li><li>软件赛：Python程序设计</li>")
    assert (await manager._run_source(CONFIG, False)).new_count == 0
    page["html"] = str(page["html"]).replace("<li>学生认证</li><li>报名后院校审核与缴费</li>",
                                           "<li>报名后院校审核与缴费</li><li>学生认证</li>")
    assert (await manager._run_source(CONFIG, False)).new_count == 1


def test_yaml_monitor_stays_local_on_desktop_and_out_of_cloud_worker(monkeypatch):
    from app.config import Settings, load_yaml
    config = next(row for row in load_yaml("sources.yaml")["sources"] if row["code"] == "lqb")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(runner_module, "get_settings", lambda: Settings(deployment_role="desktop"))
    with Session(engine) as db:
        CrawlerManager._sync_sources(db, [config])
        source = db.scalar(select(Source))
        assert source.parser == "lqb" and source.cloud_source_id is None
        assert CrawlerManager._load_source_configs(db)[0]["effective_execution"] == "local"
        source.enabled = False
        db.commit()
        CrawlerManager._sync_sources(db, [config])
        assert not source.enabled  # sync must not reset the user's toggle
        monkeypatch.setattr(runner_module, "get_settings", lambda: Settings(deployment_role="cloud"))
        assert CrawlerManager._load_source_configs(db) == []
    engine.dispose()
