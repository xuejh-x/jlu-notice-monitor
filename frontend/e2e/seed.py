from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256

from app.database import Base, SessionLocal, engine
from app.models import Notice, NoticeSourceRelation, Source, UserState


def add_notice(
    db,
    *,
    notice_id: int,
    source: Source,
    title: str,
    content: str,
    category: str,
    score: int,
    publish_date: date,
    deadline: date | None = None,
    is_read: bool = False,
    is_favorite: bool = False,
) -> None:
    url = f"https://example.test/notices/{notice_id}"
    content_hash = sha256(content.encode("utf-8")).hexdigest()
    notice = Notice(
        id=notice_id,
        title=title,
        normalized_title=title.lower(),
        url=url,
        canonical_url=url,
        publish_date=publish_date,
        source_id=source.id,
        publisher=source.name,
        content=content,
        content_hash=content_hash,
        category=category,
        importance_score=score,
        registration_deadline=deadline,
        target_students="全体在校学生",
        registration_method="在线报名",
        status="active",
    )
    notice.source_relations.append(
        NoticeSourceRelation(source=source, source_url=url, content_hash=content_hash)
    )
    notice.user_state = UserState(is_read=is_read, is_favorite=is_favorite, is_archived=False)
    db.add(notice)


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    today = date.today()
    with SessionLocal() as db:
        main_source = Source(id=1, code="e2e-main", name="E2E 教务通知", base_url="https://example.test/main", enabled=True)
        lab_source = Source(id=2, code="e2e-lab", name="E2E 科研平台", base_url="https://example.test/lab", enabled=True)
        db.add_all([main_source, lab_source])
        add_notice(db, notice_id=101, source=main_source, title="E2E 未读奖学金申请通知", content="奖学金申请面向全体学生，材料请按期提交。", category="scholarship", score=92, publish_date=today, deadline=today + timedelta(days=5))
        add_notice(db, notice_id=102, source=main_source, title="E2E 量子计算讲座报名", content="量子计算专题讲座，稳定搜索关键词为量子计算。", category="academic_lecture", score=72, publish_date=today - timedelta(days=1), is_read=True)
        add_notice(db, notice_id=103, source=lab_source, title="E2E 已收藏实验室招募", content="实验室面向本科生招募科研助理。", category="research", score=84, publish_date=today - timedelta(days=2), is_read=True, is_favorite=True)
        add_notice(db, notice_id=104, source=main_source, title="E2E 蓝桥杯竞赛通知", content="蓝桥杯校内选拔报名安排。", category="algorithm_competition", score=88, publish_date=today - timedelta(days=3), deadline=today + timedelta(days=12))
        add_notice(db, notice_id=105, source=lab_source, title="E2E 普通校园活动", content="校园活动报名与签到说明。", category="campus_activity", score=35, publish_date=today - timedelta(days=4), is_read=True)
        db.commit()


if __name__ == "__main__":
    main()
