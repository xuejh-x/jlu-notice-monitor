from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import Notice, NoticeSourceRelation, Source, UserState


def test_notice_api_and_dashboard() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    source = Source(code="ccst", name="计算机学院", base_url="https://ccst.jlu.edu.cn")
    oa = Source(
        code="oa",
        name="吉林大学 OA 校内通知",
        base_url="https://oa.jlu.edu.cn",
        enabled=True,
        ownership="OFFICIAL_CLOUD",
        source_type="official",
        parser="oa_public",
        auth_type="none",
        source_scope="official",
        execution="cloud",
        cloud_policy="force_enabled",
    )
    session.add_all([source, oa])
    session.flush()
    notice = Notice(
        title="ICPC 校内选拔",
        normalized_title="icpc校内选拔",
        url="https://ccst.jlu.edu.cn/info/1.htm",
        canonical_url="https://ccst.jlu.edu.cn/info/1.htm",
        source_id=source.id,
        content="报名通知",
        content_hash="a" * 64,
        category="algorithm_competition",
        importance_score=95,
    )
    session.add(notice)
    session.flush()
    session.add_all([
        NoticeSourceRelation(
            notice_id=notice.id,
            source_id=source.id,
            source_url=notice.url,
            content_hash=notice.content_hash,
        ),
        UserState(notice_id=notice.id),
    ])
    session.commit()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/notices", params={"category": "algorithm_competition", "min_score": 70})
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["sources"][0]["code"] == "ccst"
        source_payload = client.get("/api/sources").json()
        oa_payload = next(item for item in source_payload if item["code"] == "oa")
        assert oa_payload["status"] == "unconfigured"
        assert oa_payload["auth_required"] is False
        assert "登录" not in str(oa_payload["message"] or "")
        assert client.get("/api/dashboard").status_code == 200
        assert client.post(f"/api/notices/{notice.id}/favorite").json()["is_favorite"] is True
        assert client.post(f"/api/notices/{notice.id}/unread").json()["is_read"] is False
        unread_detail = client.get(f"/api/notices/{notice.id}").json()
        assert unread_detail["is_read"] is False
        assert unread_detail["is_favorite"] is True
        assert client.post(f"/api/notices/{notice.id}/read").json()["is_read"] is True
        assert client.post("/api/notices/read-all").json() == {"updated": 0}
        client.post(f"/api/notices/{notice.id}/unread")
        assert client.post("/api/notices/read-all").json() == {"updated": 1}
        assert client.post("/api/notices/read-all").json() == {"updated": 0}
        read_detail = client.get(f"/api/notices/{notice.id}").json()
        assert read_detail["is_read"] is True
        assert read_detail["is_favorite"] is True
    finally:
        app.dependency_overrides.clear()
        session.close()
