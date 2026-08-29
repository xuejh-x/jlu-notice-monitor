from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classifier import classify_notice, score_importance
from app.config import get_settings, load_yaml
from app.database import SessionLocal, init_db
from app.models import Attachment, Notice, NoticeSourceRelation, NoticeUpdate, Source, UserState
from app.schemas.notice import NoticeCandidate
from app.services.dates import extract_dates
from app.services.deduplication import find_duplicate
from app.services.metadata import extract_notice_metadata
from app.services.normalization import canonicalize_url, content_hash, normalize_title
from app.sources import build_source
from app.sources.base import LoginExpiredError
from app.paths import get_cache_dir

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class SourceRunResult:
    source: str
    fetched: int = 0
    new_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class CrawlRunResult:
    started_at: datetime
    finished_at: datetime | None = None
    new_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    source_results: list[SourceRunResult] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        if not self.finished_at:
            return None
        return round((self.finished_at - self.started_at).total_seconds(), 3)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["duration_seconds"] = self.duration_seconds
        return value


class CrawlerAlreadyRunning(RuntimeError):
    pass


class CrawlerManager:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self._lock = asyncio.Lock()
        if cache_dir is None:
            settings = get_settings()
            cache_dir = get_cache_dir(settings.environment, settings.app_data_dir)
        self._lock_file = cache_dir / "crawler.lock"
        self._status_file = cache_dir / "crawler_status.json"
        self.last_result: CrawlRunResult | None = None
        self.current_started_at: datetime | None = None
        self._task: asyncio.Task[CrawlRunResult] | None = None

    @property
    def running(self) -> bool:
        return self._lock.locked() or (self._task is not None and not self._task.done())

    def start(self, source_code: str | None = None) -> None:
        if self.running:
            raise CrawlerAlreadyRunning("crawler is already running")
        self._task = asyncio.create_task(self.run(source_code=source_code))
        self._task.add_done_callback(self._log_task_result)

    async def shutdown(self) -> None:
        task = self._task
        if task is not None and not task.done():
            logger.info("cancelling background crawler during shutdown")
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._task = None

    @staticmethod
    def _log_task_result(task: asyncio.Task[CrawlRunResult]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("background crawler task cancelled")
        except Exception:
            logger.exception("background crawler task failed")

    def status(self) -> dict[str, Any]:
        result = self.last_result
        if result is None and self._status_file.exists():
            try:
                saved = json.loads(self._status_file.read_text(encoding="utf-8"))
                saved["running"] = self.running
                saved["current_started_at"] = self.current_started_at
                return saved
            except (OSError, ValueError, TypeError):
                logger.warning("could not read persisted crawler status", exc_info=True)
        return {
            "running": self.running,
            "current_started_at": self.current_started_at,
            "last_run": result.finished_at if result else None,
            "last_duration": result.duration_seconds if result else None,
            "new_count": result.new_count if result else 0,
            "updated_count": result.updated_count if result else 0,
            "source_results": [asdict(item) for item in result.source_results] if result else [],
        }

    def _acquire_file_lock(self) -> None:
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        stale_hours = float(load_yaml("settings.yaml").get("crawler", {}).get("stale_lock_hours", 4))
        if self._lock_file.exists():
            age = time.time() - self._lock_file.stat().st_mtime
            if age > stale_hours * 3600:
                self._lock_file.unlink(missing_ok=True)
        try:
            descriptor = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise CrawlerAlreadyRunning("crawler is already running") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(f"pid={os.getpid()} started={datetime.now().isoformat()}\n")

    async def run(self, source_code: str | None = None, bootstrap: bool = False) -> CrawlRunResult:
        if self._lock.locked():
            raise CrawlerAlreadyRunning("crawler is already running")
        async with self._lock:
            self._acquire_file_lock()
            self.current_started_at = utcnow()
            result = CrawlRunResult(started_at=self.current_started_at)
            try:
                init_db()
                configs = load_yaml("sources.yaml").get("sources", [])
                if source_code:
                    configs = [item for item in configs if item.get("code") == source_code]
                    if not configs:
                        raise ValueError(f"Unknown source: {source_code}")
                configs = [
                    item for item in configs
                    if item.get("enabled", True)
                ]
                with SessionLocal() as db:
                    self._sync_sources(db, load_yaml("sources.yaml").get("sources", []))
                for config in configs:
                    source_result = await self._run_source(config, bootstrap)
                    result.source_results.append(source_result)
                    result.new_count += source_result.new_count
                    result.updated_count += source_result.updated_count
                    result.unchanged_count += source_result.unchanged_count
            finally:
                result.finished_at = utcnow()
                self.last_result = result
                self.current_started_at = None
                self._status_file.parent.mkdir(parents=True, exist_ok=True)
                self._status_file.write_text(
                    json.dumps(self.status(), ensure_ascii=False, default=str, indent=2),
                    encoding="utf-8",
                )
                self._lock_file.unlink(missing_ok=True)
                logger.info(
                    "crawler finished duration=%.3fs new=%d updated=%d unchanged=%d",
                    result.duration_seconds or 0,
                    result.new_count,
                    result.updated_count,
                    result.unchanged_count,
                )
            return result

    @staticmethod
    def _sync_sources(db: Session, configs: list[dict[str, Any]]) -> None:
        for config in configs:
            source = db.scalar(select(Source).where(Source.code == config["code"]))
            if source is None:
                source = Source(
                    code=config["code"], name=config["name"], base_url=config["base_url"]
                )
                db.add(source)
            source.name = config["name"]
            source.base_url = config["base_url"]
            source.enabled = bool(config.get("enabled", True))
        db.commit()

    async def _run_source(self, config: dict[str, Any], bootstrap: bool) -> SourceRunResult:
        code = str(config["code"])
        run_result = SourceRunResult(source=code)
        adapter = build_source(config)
        logger.info("source=%s started", code)
        with SessionLocal() as db:
            db_source = db.scalar(select(Source).where(Source.code == code))
            assert db_source is not None
            db_source.last_checked_at = utcnow()
            db.commit()
            try:
                items = await adapter.fetch_list()
                run_result.fetched = len(items)
                logger.info("source=%s list_count=%d", code, len(items))
                for item in items:
                    try:
                        detail = await adapter.fetch_detail(item)
                        state = self._persist_candidate(db, db_source, detail, bootstrap)
                        if state == "NEW":
                            run_result.new_count += 1
                        elif state == "UPDATED":
                            run_result.updated_count += 1
                        else:
                            run_result.unchanged_count += 1
                    except Exception as exc:  # one bad notice must not stop a source
                        message = f"{item.url}: {type(exc).__name__}: {exc}"
                        run_result.errors.append(message)
                        logger.warning("source=%s detail_error=%s", code, message)
                        db.rollback()
                db_source.last_success_at = utcnow()
                db_source.last_error = None
                db_source.consecutive_errors = 0
            except LoginExpiredError:
                db_source.last_error = "OA_LOGIN_EXPIRED"
                db_source.consecutive_errors += 1
                run_result.errors.append("OA_LOGIN_EXPIRED")
                logger.error("source=%s OA_LOGIN_EXPIRED", code)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                db_source.last_error = message
                db_source.consecutive_errors += 1
                run_result.errors.append(message)
                logger.error("source=%s failed=%s", code, message)
            finally:
                db.commit()
                await adapter.close()
        return run_result

    @staticmethod
    def _persist_candidate(
        db: Session, source: Source, candidate: NoticeCandidate, bootstrap: bool
    ) -> str:
        now = utcnow()
        normalized = normalize_title(candidate.title)
        canonical = canonicalize_url(candidate.url)
        digest = content_hash(candidate.title, candidate.content)
        dates = extract_dates(candidate.content, candidate.publish_date)
        category = classify_notice(candidate.title, candidate.content)
        score = score_importance(
            candidate.title, candidate.content, category, dates.registration_deadline
        )
        target_students, registration_method, competition_level = extract_notice_metadata(
            candidate.content
        )
        notice = find_duplicate(db, normalized, canonical, candidate.publish_date)
        existing_relation = None
        if notice:
            existing_relation = db.scalar(
                select(NoticeSourceRelation).where(
                    NoticeSourceRelation.notice_id == notice.id,
                    NoticeSourceRelation.source_id == source.id,
                    NoticeSourceRelation.source_url == candidate.url,
                )
            )
        state = "UNCHANGED"
        if notice is None:
            notice = Notice(
                title=candidate.title,
                normalized_title=normalized,
                url=candidate.url,
                canonical_url=canonical,
                publish_date=candidate.publish_date,
                source_id=source.id,
                publisher=candidate.publisher,
                content=candidate.content,
                content_hash=digest,
                category=category,
                importance_score=score,
                status="baseline" if bootstrap else "active",
                registration_start=dates.registration_start,
                registration_deadline=dates.registration_deadline,
                event_start=dates.event_start,
                event_end=dates.event_end,
                target_students=target_students,
                registration_method=registration_method,
                competition_level=competition_level,
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            )
            db.add(notice)
            db.flush()
            recent_cutoff = date.today() - timedelta(days=get_settings().bootstrap_recent_days)
            recent_important = bool(
                candidate.publish_date
                and candidate.publish_date >= recent_cutoff
                and score >= 70
            )
            db.add(
                UserState(
                    notice_id=notice.id,
                    is_read=bootstrap and not recent_important,
                )
            )
            state = "UNCHANGED" if bootstrap else "NEW"
        elif existing_relation and existing_relation.content_hash != digest:
            old_hash = existing_relation.content_hash
            db.add(
                NoticeUpdate(
                    notice_id=notice.id,
                    old_hash=old_hash,
                    new_hash=digest,
                    summary=f"来源 {source.code} 的正文内容发生变化",
                )
            )
            if notice.url == candidate.url:
                notice.title = candidate.title
                notice.normalized_title = normalized
                notice.content = candidate.content
                notice.content_hash = digest
                notice.publisher = candidate.publisher
                notice.category = category
                notice.importance_score = score
                notice.registration_start = dates.registration_start
                notice.registration_deadline = dates.registration_deadline
                notice.event_start = dates.event_start
                notice.event_end = dates.event_end
                notice.target_students = target_students
                notice.registration_method = registration_method
                notice.competition_level = competition_level
            notice.updated_at = now
            state = "UPDATED"
        notice.last_seen_at = now
        if notice.target_students is None:
            notice.target_students = target_students
        if notice.registration_method is None:
            notice.registration_method = registration_method
        if notice.competition_level is None:
            notice.competition_level = competition_level
        if existing_relation:
            existing_relation.last_seen_at = now
            existing_relation.content_hash = digest
        else:
            db.add(
                NoticeSourceRelation(
                    notice_id=notice.id,
                    source_id=source.id,
                    source_url=candidate.url,
                    content_hash=digest,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
        for attachment in candidate.attachments:
            exists = db.scalar(
                select(Attachment).where(
                    Attachment.notice_id == notice.id, Attachment.url == attachment.url
                )
            )
            if exists is None:
                db.add(
                    Attachment(
                        notice_id=notice.id,
                        filename=attachment.filename,
                        url=attachment.url,
                        type=attachment.type,
                    )
                )
        db.commit()
        return state


crawler_manager = CrawlerManager()
