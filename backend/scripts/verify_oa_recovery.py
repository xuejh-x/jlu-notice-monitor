"""Verify real OA Cloud -> Local recovery using only an in-memory database.

Requires JLU_DATABASE_URL=sqlite://, JLU_DEPLOYMENT_ROLE=desktop,
and an explicit isolated JLU_APP_DATA_DIR. Does not start an application/server.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.config import get_settings, load_yaml
from app.paths import BACKEND_DIR


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = get_settings()
    if (settings.effective_database_url not in {"sqlite://", "sqlite:///:memory:"}
            or not settings.app_data_dir
            or settings.effective_deployment_role != "desktop"
            or not Path(settings.app_data_dir).resolve().is_relative_to((BACKEND_DIR / "build").resolve())):
        parser.error("In-memory SQLite, app data dir under backend/build, and desktop role required")

    # Import database-owning modules only after checking the isolation settings.
    from app.crawler.runner import CrawlerManager
    from app.database import SessionLocal, close_db, init_db
    from app.logging_config import configure_logging
    from app.models import Favorite, Notice, NoticeSourceRelation, Source, UserState

    configure_logging(log_dir=Path(settings.app_data_dir) / "logs")
    init_db()
    local = next(x for x in load_yaml("sources.yaml")["sources"] if x["code"] == "oa")
    config = {**local, "parser": "cloud_feed", "fallback_parser": "oa_public",
              "effective_execution": "cloud", "execution_policy": "cloud_preferred"}
    with SessionLocal() as db:
        db.add(Source(code="oa", name=local["name"], base_url=local["base_url"],
                      ownership="OFFICIAL_CLOUD"))
        db.commit()
    manager = CrawlerManager(cache_dir=Path(settings.app_data_dir) / "cache")
    results = []
    try:
        first = await manager._run_source(config, False)
        assert first.status == "success", first.errors
        assert [(a.execution, a.status) for a in first.attempts] == [("cloud", "failure"), ("local", "success")]
        assert first.fallback_reason == "PUBLIC_FEED_NOT_CONFIGURED"
        results.append(asdict(first))
        with SessionLocal() as db:
            ids = db.scalars(select(Notice.id).order_by(Notice.id)).all()
            assert len(ids) >= 2, "Need two real notices to check read and unread state"
            for index, notice_id in enumerate(ids):
                state = db.scalar(select(UserState).where(UserState.notice_id == notice_id))
                state.is_read = index != 0
                state.is_favorite = index == 0
            db.add(Favorite(notice_id=ids[0]))
            db.commit()
            states = [(s.notice_id, s.is_read, s.is_favorite, s.updated_at)
                      for s in db.scalars(select(UserState).order_by(UserState.notice_id))]
            relations = [(r.id, r.notice_id, r.origin_item_key)
                         for r in db.scalars(select(NoticeSourceRelation).order_by(NoticeSourceRelation.id))]
        for _ in range(2):
            result = await manager._run_source(config, False)
            assert result.status == "success" and result.new_count == 0, result.errors
            assert result.detail_skipped == len(ids)
            results.append(asdict(result))
        with SessionLocal() as db:
            assert db.scalars(select(Notice.id).order_by(Notice.id)).all() == ids
            assert [(s.notice_id, s.is_read, s.is_favorite, s.updated_at)
                    for s in db.scalars(select(UserState).order_by(UserState.notice_id))] == states
            assert [(r.id, r.notice_id, r.origin_item_key)
                    for r in db.scalars(select(NoticeSourceRelation).order_by(NoticeSourceRelation.id))] == relations
            assert db.scalars(select(Favorite.notice_id)).all() == [ids[0]]
            source = db.scalar(select(Source).where(Source.code == "oa"))
            assert source.health_state == "healthy" and source.last_error is None
            assert source.last_error_code is None and source.consecutive_errors == 0
        report = {"utc_time": datetime.now(timezone.utc).isoformat(), "status": "PASS",
                  "database": "in-memory SQLite", "default_domain_path": True,
                  "notice_count": len(ids), "read_unread_favorite_and_timestamps_preserved": True,
                  "notice_ids_and_relation_keys_preserved": True, "runs": results}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await manager.shutdown()
        close_db()


if __name__ == "__main__":
    asyncio.run(main())
