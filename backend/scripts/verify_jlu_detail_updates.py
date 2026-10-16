"""Offline R1/R2 acceptance evidence; run from the isolated final source copy."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch


async def verify(output: Path) -> None:
    backend = Path(__file__).resolve().parents[1]
    if "build" not in backend.parts or not (backend / ".env").is_file():
        raise RuntimeError("Run the script from verify_jlu_b1.py's isolated final source copy")
    output.parent.mkdir(parents=True, exist_ok=True)
    for key in list(os.environ):
        if key.startswith(("JLU_", "NOTICE_HUB_")):
            del os.environ[key]
    os.environ.update(JLU_DATABASE_URL="sqlite://", JLU_SCHEDULER_ENABLED="false",
                      JLU_STARTUP_SYNC_ENABLED="false", JLU_APP_DATA_DIR=str(output.parent / "runtime"))
    sys.path.insert(0, str(backend))
    import httpx
    from sqlalchemy import create_engine, event, select
    from sqlalchemy.orm import Session
    import app
    import app.crawler.runner as runner
    from app.config import Settings, get_settings
    from app.database import Base
    from app.database.session import engine as application_engine
    from app.models import Attachment, Favorite, Notice, NoticeSourceRelation, NoticeUpdate, Source, UserState
    from app.schemas.notice import AttachmentData, NoticeCandidate
    from app.services.detail_observation import load_observation, relation_key

    assert Path(app.__file__).resolve().is_relative_to(backend)
    assert get_settings().effective_database_url == "sqlite://"
    def forbidden(*args, **kwargs):
        raise RuntimeError("HTTP_OR_APPLICATION_DATABASE_FORBIDDEN")
    event.listen(application_engine, "connect", forbidden)
    settings = Settings(_env_file=None, database_url="sqlite://", deployment_role="standalone",
                        detail_recheck_delay_seconds=0)
    def attachment(name):
        return AttachmentData(filename=name + ".pdf", url=f"https://test.invalid/{name}.pdf", type="pdf")
    rows = []
    real_time = datetime.now(timezone.utc)
    try:
        with patch.object(httpx.AsyncClient, "send", forbidden), patch.object(socket.socket, "connect", forbidden):
            for scenario in ("body-only", "attachment-add", "attachment-replace", "attachment-remove", "failure-recovery"):
                clock = [real_time.replace(tzinfo=None)]
                test_engine = create_engine("sqlite://")
                Base.metadata.create_all(test_engine)
                manager = runner.CrawlerManager(output.parent / "runtime")
                original = NoticeCandidate(public_id="fixture:stable-id", title="独立验收通知",
                    url=f"https://test.invalid/info/1/{scenario}.htm", publish_date=clock[0].date(),
                    publisher="独立假来源", content="原通知正文", attachments=[attachment("old")], attachments_complete=True)
                changes = {
                    "body-only": {"content": "原通知正文；补充新的报名要求"},
                    "attachment-add": {"attachments": [attachment("old"), attachment("new")]},
                    "attachment-replace": {"attachments": [attachment("new")]},
                    "attachment-remove": {"attachments": []},
                    "failure-recovery": {"content": "恢复后新正文", "attachments": [attachment("new")]},
                }[scenario]
                revised = original.model_copy(update=changes)
                class Fake:
                    current = original
                    calls = 0
                    fail = False
                    async def fetch_list(self):
                        return [original.model_copy(update={"content": "", "attachments": [], "attachments_complete": False})]
                    async def fetch_detail(self, item):
                        self.calls += 1
                        if self.fail:
                            raise RuntimeError("FIXTURE_DETAIL_UNAVAILABLE")
                        return self.current
                    async def close(self):
                        pass
                adapter = Fake()
                with Session(test_engine, autoflush=False, expire_on_commit=False) as db, \
                        patch.object(runner, "get_settings", return_value=settings), \
                        patch.object(runner, "utcnow", side_effect=lambda: clock[0]), \
                        patch.object(runner, "build_source", return_value=adapter):
                    source = Source(code="fixture", name="独立假来源", base_url="https://test.invalid")
                    db.add(source); db.commit()
                    async def execute(bootstrap=False):
                        result = runner.SourceRunResult(source=source.code)
                        await manager._execute_source_attempt(db, source, {"code": source.code}, bootstrap, result, "local")
                        return asdict(result)
                    first = await execute(True)
                    notice = db.scalar(select(Notice))
                    user = db.scalar(select(UserState))
                    user.is_read = user.is_favorite = True
                    db.add(Favorite(notice_id=notice.id)); db.commit()
                    identity = (notice.id, notice.public_id, notice.canonical_url, notice.source_id, notice.first_seen_at)
                    relation = db.scalar(select(NoticeSourceRelation))
                    token = relation_key(source.id, relation.origin_item_key)
                    success_before = load_observation(db, notice)["relations"][token]["checked_at"]
                    adapter.current = revised
                    clock[0] += timedelta(hours=12)
                    recent = await execute()
                    assert recent["detail_skipped"] == 1 and adapter.calls == 1
                    clock[0] += timedelta(hours=12)
                    failure = None
                    if scenario == "failure-recovery":
                        adapter.fail = True
                        failure = await execute()
                        assert failure["errors"] and notice.content == original.content and notice.version == 1
                        assert load_observation(db, notice)["relations"][token]["checked_at"] == success_before
                        adapter.fail = False
                    final = await execute()
                    attachments = [{"filename": a.filename, "url": a.url, "type": a.type}
                                   for a in db.scalars(select(Attachment))]
                    assert final["updated_count"] == 1 and notice.content == revised.content and notice.version == 2
                    assert {a["url"] for a in attachments} == {a.url for a in revised.attachments}
                    assert identity == (notice.id, notice.public_id, notice.canonical_url, notice.source_id, notice.first_seen_at)
                    assert user.is_read and user.is_favorite and db.scalar(select(Favorite)).notice_id == notice.id
                    assert len(db.scalars(select(NoticeSourceRelation)).all()) == 1
                    updates = db.scalars(select(NoticeUpdate)).all()
                    assert len(updates) == 1
                    repeated = await execute()
                    assert repeated["updated_count"] == 0 and notice.version == 2
                    rows.append({"scenario": scenario, "url": original.url, "verified_at": datetime.now(timezone.utc).isoformat(),
                        "result": "passed", "reason": "unchanged list rechecked after TTL; one revision; identity and read/favorite/source preserved",
                        "simulated_time": clock[0].isoformat(), "first_run": first, "recent_run": recent,
                        "failure_run": failure, "final_run": final, "repeat_run": repeated, "detail_calls": adapter.calls,
                        "body_before": original.content, "body_after": notice.content,
                        "attachments_before": [a.model_dump() for a in original.attachments], "attachments_after": attachments,
                        "notice_id": notice.id, "public_id": notice.public_id, "version": notice.version,
                        "identity_preserved": True, "read_and_favorite_preserved": True, "source_relations": 1,
                        "success_checkpoint_before": success_before, "success_checkpoint_after": load_observation(db, notice)["relations"][token]["checked_at"],
                        "updates": [{"old_hash": u.old_hash, "new_hash": u.new_hash, "summary": u.summary} for u in updates]})
                test_engine.dispose()
    finally:
        event.remove(application_engine, "connect", forbidden)
    evidence = {"verified_at": real_time.isoformat(), "isolated_backend": str(backend), "database": "sqlite://",
        "method": "independent memory databases, fake adapters, denied HTTP and application DB connections",
        "http_requests": 0, "production_db_connections": 0, "passed": len(rows), "scenarios": rows,
        "code_sha256": {str(p.relative_to(backend)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [backend / "app/crawler/runner.py", backend / "app/services/detail_observation.py",
                                  backend / "app/parsers/html.py", backend / "app/schemas/notice.py", Path(__file__)]},
        "limits": "Synthetic offline acceptance; not a live website, Cloud deployment, feed service or installed client validation. Legacy unattributed references remain protected."}
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(rows)} offline acceptance scenarios passed; HTTP=0; production DB connections=0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(verify(parser.parse_args().output.resolve()))
