from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.crawler.runner import CrawlerManager
from app.database import Base
from app.models import Notice, NoticeSourceRelation, NoticeUpdate, Source, UserState
from app.schemas.notice import NoticeCandidate
from app.services.deduplication import find_duplicate, title_similarity
from app.services.normalization import normalize_title


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_title_similarity_and_cross_source_dedup() -> None:
    assert title_similarity("第41次ccfcsp认证报名", "第41次ccfcsp认证报名") == 1
    with make_session() as db:
        source = Source(code="ccst", name="计算机学院", base_url="https://ccst.jlu.edu.cn")
        db.add(source)
        db.flush()
        notice = Notice(
            title="第41次 CCF CSP 认证报名通知",
            normalized_title=normalize_title("第41次 CCF CSP 认证报名通知"),
            url="https://ccst.jlu.edu.cn/info/1.htm",
            canonical_url="https://ccst.jlu.edu.cn/info/1.htm",
            publish_date=date(2026, 3, 11),
            source_id=source.id,
            content="正文",
            content_hash="x" * 64,
        )
        db.add(notice)
        db.commit()
        found = find_duplicate(
            db,
            normalize_title("关于第41次 CCF CSP 认证报名的通知"),
            "https://other.jlu.edu.cn/info/2.htm",
            date(2026, 3, 12),
        )
        assert found is not None
        assert found.id == notice.id


def test_persist_new_unchanged_and_updated() -> None:
    with make_session() as db:
        source = Source(code="ccst", name="计算机学院", base_url="https://ccst.jlu.edu.cn")
        db.add(source)
        db.commit()
        first = NoticeCandidate(title="CSP报名通知", url="https://ccst.jlu.edu.cn/info/1.htm", content="原正文")
        assert CrawlerManager._persist_candidate(db, source, first, False) == "NEW"
        assert CrawlerManager._persist_candidate(db, source, first, False) == "UNCHANGED"
        changed = first.model_copy(update={"content": "更新后的正文"})
        assert CrawlerManager._persist_candidate(db, source, changed, False) == "UPDATED"
        assert len(db.scalars(select(Notice)).all()) == 1
        assert len(db.scalars(select(NoticeSourceRelation)).all()) == 1
        assert len(db.scalars(select(NoticeUpdate)).all()) == 1


def test_cross_source_versions_keep_independent_hashes() -> None:
    with make_session() as db:
        first_source = Source(code="cse", name="网安学院", base_url="https://cse.jlu.edu.cn")
        second_source = Source(code="csw", name="软件学院", base_url="https://csw.jlu.edu.cn")
        db.add_all([first_source, second_source])
        db.commit()
        first = NoticeCandidate(
            title="关于开源安全奖励计划的通知",
            url="https://cse.jlu.edu.cn/info/1.htm",
            content="网安学院版本",
        )
        second = NoticeCandidate(
            title="开源安全奖励计划通知",
            url="https://csw.jlu.edu.cn/info/2.htm",
            content="软件学院版本",
        )
        assert CrawlerManager._persist_candidate(db, first_source, first, False) == "NEW"
        assert CrawlerManager._persist_candidate(db, second_source, second, False) == "UNCHANGED"
        assert CrawlerManager._persist_candidate(db, first_source, first, False) == "UNCHANGED"
        assert CrawlerManager._persist_candidate(db, second_source, second, False) == "UNCHANGED"
        assert len(db.scalars(select(Notice)).all()) == 1
        assert len(db.scalars(select(NoticeUpdate)).all()) == 0


def test_bootstrap_marks_history_as_baseline_and_read() -> None:
    with make_session() as db:
        source = Source(code="ccst", name="计算机学院", base_url="https://ccst.jlu.edu.cn")
        db.add(source)
        db.commit()
        item = NoticeCandidate(
            title="历史教学通知",
            url="https://ccst.jlu.edu.cn/info/old.htm",
            content="历史正文",
            publish_date=date(2020, 1, 1),
        )
        assert CrawlerManager._persist_candidate(db, source, item, True) == "UNCHANGED"
        notice = db.scalar(select(Notice))
        state = db.scalar(select(UserState))
        assert notice is not None and notice.status == "baseline"
        assert state is not None and state.is_read is True
