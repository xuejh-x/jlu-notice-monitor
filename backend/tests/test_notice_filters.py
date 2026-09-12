from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Notice, NoticeSourceRelation, Source, UserState


@pytest.fixture
def notice_client() -> TestClient:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    ccst = Source(code="ccst", name="计算机学院", base_url="https://ccst.jlu.edu.cn")
    cse = Source(code="cse", name="网络安全学院", base_url="https://cse.jlu.edu.cn")
    session.add_all([ccst, cse])
    session.flush()
    today = date.today()
    rows = [
        ("蓝桥杯报名通知", "算法竞赛报名", "algorithm_competition", ccst, today + timedelta(days=1), True, True),
        ("CTF 校内赛", "网络安全竞赛", "cybersecurity_competition", cse, today - timedelta(days=1), False, False),
        ("实验室招募", "科研项目", "research", ccst, None, True, False),
        ("CSP 认证", "程序设计竞赛", "algorithm_competition", cse, today + timedelta(days=10), False, True),
        ("程序设计训练", "算法训练", "algorithm_competition", ccst, None, None, None),
    ]
    for index, (title, content, category, source, deadline, favorite, read) in enumerate(rows):
        notice = Notice(
            title=title,
            normalized_title=title.casefold(),
            url=f"https://example.com/{index}",
            canonical_url=f"https://example.com/{index}",
            publish_date=today - timedelta(days=index),
            source_id=source.id,
            content=content,
            content_hash=str(index) * 64,
            category=category,
            importance_score=90 - index * 10,
            registration_deadline=deadline,
        )
        session.add(notice)
        session.flush()
        session.add(NoticeSourceRelation(
            notice_id=notice.id,
            source_id=source.id,
            source_url=notice.url,
            content_hash=notice.content_hash,
        ))
        if favorite is not None and read is not None:
            session.add(UserState(notice_id=notice.id, is_favorite=favorite, is_read=read))
    session.commit()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_default_and_explicit_pagination(notice_client: TestClient) -> None:
    default = notice_client.get("/api/notices").json()
    assert (default["page"], default["page_size"], default["total"], default["total_pages"]) == (1, 20, 5, 1)
    assert (default["total_count"], default["unread_count"], default["all_count"]) == (5, 3, 5)
    second = notice_client.get("/api/notices", params={"page": 2, "page_size": 2}).json()
    assert second["page"] == 2
    assert second["total_pages"] == 3
    assert len(second["items"]) == 2


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"favorite": "true"}, 2),
        ({"favorite": "false"}, 3),
        ({"read": "true"}, 2),
        ({"read": "false"}, 3),
        ({"category": "algorithm_competition"}, 3),
        ({"source": "cse"}, 2),
        ({"min_score": "80"}, 2),
        ({"date_from": date.today().isoformat()}, 1),
        ({"deadline_status": "urgent"}, 1),
        ({"deadline_status": "expired"}, 1),
        ({"deadline_status": "unknown"}, 2),
        ({"q": "蓝桥杯"}, 1),
    ],
)
def test_individual_filters(notice_client: TestClient, params: dict[str, str], expected: int) -> None:
    response = notice_client.get("/api/notices", params=params)
    assert response.status_code == 200
    assert response.json()["total"] == expected


def test_combined_filters_and_empty_result(notice_client: TestClient) -> None:
    response = notice_client.get("/api/notices", params={
        "favorite": "true",
        "read": "true",
        "category": "algorithm_competition",
        "source": "ccst",
        "deadline_status": "urgent",
        "q": "蓝桥杯",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["total_count"] == 1
    assert result["unread_count"] == 0
    assert result["all_count"] == 5
    assert result["items"][0]["title"] == "蓝桥杯报名通知"
    empty = notice_client.get("/api/notices", params={"q": "不存在的通知"}).json()
    assert empty["total"] == 0
    assert empty["total_pages"] == 0
    assert empty["items"] == []


def test_category_group_and_legacy_keyword(notice_client: TestClient) -> None:
    grouped = notice_client.get(
        "/api/notices",
        params={"category": "algorithm_competition,cybersecurity_competition"},
    ).json()
    assert grouped["total"] == 4
    legacy = notice_client.get("/api/notices", params={"keyword": "CTF"}).json()
    assert legacy["total"] == 1


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
def test_invalid_pagination_returns_422(notice_client: TestClient, params: dict[str, int]) -> None:
    assert notice_client.get("/api/notices", params=params).status_code == 422


def test_global_counts_are_independent_and_include_implicit_unread(notice_client: TestClient) -> None:
    dashboard = notice_client.get("/api/dashboard").json()
    assert dashboard["total_count"] == 5
    assert dashboard["unread"] == 3
    important = dashboard["important"]
    deadlines = dashboard["upcoming_deadlines"]

    unread_list = notice_client.get("/api/notices", params={"read": "false"}).json()
    assert unread_list["total"] == 3
    refreshed = notice_client.get("/api/dashboard").json()
    assert refreshed["total_count"] == 5
    assert refreshed["unread"] == 3
    assert refreshed["important"] == important
    assert refreshed["upcoming_deadlines"] == deadlines


def test_filtered_pagination_uses_current_result_count(notice_client: TestClient) -> None:
    first = notice_client.get(
        "/api/notices",
        params={"category": "algorithm_competition", "page": 1, "page_size": 2},
    ).json()
    second = notice_client.get(
        "/api/notices",
        params={"category": "algorithm_competition", "page": 2, "page_size": 2},
    ).json()

    assert (first["total_count"], first["total_pages"], len(first["items"])) == (3, 2, 2)
    assert (second["total_count"], second["total_pages"], len(second["items"])) == (3, 2, 1)
    assert first["all_count"] == second["all_count"] == 5


def test_clearing_filters_restores_all_notices(notice_client: TestClient) -> None:
    filtered = notice_client.get("/api/notices", params={"source": "cse"}).json()
    cleared = notice_client.get("/api/notices").json()

    assert filtered["total_count"] == 2
    assert cleared["total_count"] == cleared["all_count"] == 5
