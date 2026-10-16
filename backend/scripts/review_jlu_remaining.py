"""Offline remaining-risk reproduction with fake HTTP and independent memory DB."""
import asyncio
from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-remaining-review"
os.environ["JLU_DATABASE_URL"] = "sqlite://"
os.environ["JLU_APP_DATA_DIR"] = str(OUT / "runtime")
os.environ["JLU_SCHEDULER_ENABLED"] = "false"
os.environ["JLU_STARTUP_SYNC_ENABLED"] = "false"
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from app.config import Settings
from app.database import Base
from app.database.session import engine as application_engine
from app.models import Attachment, Favorite, Notice, Source, UserState
from app.schemas.notice import AttachmentData, NoticeCandidate
from app.crawler.runner import CrawlerManager, SourceRunResult
import app.crawler.runner as runner


async def main():
    assert str(application_engine.url) == "sqlite://"
    def forbid(*_):
        raise RuntimeError("APPLICATION_DATABASE_FORBIDDEN")
    event.listen(application_engine, "connect", forbid)
    settings = Settings(_env_file=None, database_url="sqlite://", deployment_role="standalone", app_data_dir=str(OUT / "runtime"))
    test_engine = create_engine("sqlite://")
    Base.metadata.create_all(test_engine)
    manager = CrawlerManager(OUT / "runtime")
    old = NoticeCandidate(title="独立测试通知", url="https://test.invalid/info/1/2.htm", publish_date=date.today(), content="原通知正文",
        attachments=[AttachmentData(filename="原附件.pdf", url="https://test.invalid/old.pdf", type="pdf")])
    changed = old.model_copy(update={"content": "原通知正文；补充了新的报名要求", "attachments": [AttachmentData(filename="新附件.pdf", url="https://test.invalid/new.pdf", type="pdf")]})
    class Fake:
        current = old
        detail_calls = 0
        async def fetch_list(self):
            return [self.current.model_copy(update={"content": "", "attachments": []})]
        async def fetch_detail(self, item):
            self.detail_calls += 1
            return self.current
        async def close(self):
            pass
    adapter = Fake()
    try:
        with Session(test_engine, expire_on_commit=False) as db, patch.object(runner, "get_settings", return_value=settings), patch.object(runner, "build_source", return_value=adapter):
            source = Source(code="remaining-review", name="独立测试来源", base_url="https://test.invalid")
            db.add(source)
            db.commit()
            config = {"code": source.code, "base_url": source.base_url}
            first = SourceRunResult(source=source.code)
            await manager._execute_source_attempt(db, source, config, True, first, "local")
            notice = db.scalar(select(Notice))
            state = db.scalar(select(UserState))
            state.is_read = state.is_favorite = True
            db.add(Favorite(notice_id=notice.id))
            db.commit()
            saved_id = notice.id
            adapter.current = changed
            second = SourceRunResult(source=source.code)
            await manager._execute_source_attempt(db, source, config, False, second, "local")
            stale = {"detail_calls_first_two_runs": adapter.detail_calls, "second_run": asdict(second), "body_seen": notice.content,
                "attachment_urls": [a.url for a in db.scalars(select(Attachment))], "new_body_detected": notice.content == changed.content,
                "new_attachment_detected": bool(db.scalar(select(Attachment).where(Attachment.url == "https://test.invalid/new.pdf")))}
            # Isolate attachment-only persistence from the earlier list skip.
            attachment_only = old.model_copy(update={"attachments": changed.attachments})
            prior_version = notice.version
            result = manager._persist_candidate(db, source, attachment_only, False)
            attachment_update = {"return_state": result, "version_before": prior_version, "version_after": notice.version,
                "attachment_urls_after_replacement_snapshot": [a.url for a in db.scalars(select(Attachment))],
                "old_attachment_still_present": bool(db.scalar(select(Attachment).where(Attachment.url == "https://test.invalid/old.pdf"))),
                "same_notice_id": notice.id == saved_id, "read_and_favorite_preserved": state.is_read and state.is_favorite,
                "favorites": len(db.scalars(select(Favorite)).all())}
            assert stale["detail_calls_first_two_runs"] == 1 and not stale["new_body_detected"] and not stale["new_attachment_detected"]
            assert attachment_update["return_state"] == "UNCHANGED" and attachment_update["old_attachment_still_present"]
            assert attachment_update["same_notice_id"] and attachment_update["read_and_favorite_preserved"]
            output = {"checked_at": datetime.now(timezone.utc).isoformat(),
                "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ["backend/app/crawler/runner.py", "backend/app/services/normalization.py", "backend/scripts/review_jlu_remaining.py"]},
                "method": "two fake-adapter runs + attachment-only direct persistence; sqlite:// independent memory engine", "http_requests": 0,
                "production_db_connections": 0, "fixture_host": "test.invalid", "findings": {"unchanged_list_hides_detail_updates": stale, "attachment_only_change_not_versioned_and_old_reference_retained": attachment_update},
                "scope_limit": "Reproduces code behavior only; does not establish any real user notice has been missed; source-aware removal semantics need design"}
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "reproduction.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        test_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
