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
from app.logging_config import log_event

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class SourceRunResult:
    source: str
    status: str = "pending"
    fetched: int = 0
    detail_fetched: int = 0
    detail_skipped: int = 0
    new_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    errors: list[str] = field(default_factory=list)
    list_duration_seconds: float = 0.0
    detail_duration_seconds: float = 0.0
    parse_db_duration_seconds: float = 0.0


@dataclass
class CrawlRunResult:
    started_at: datetime
    trigger: str = "manual"
    finished_at: datetime | None = None
    new_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    status: str = "running"
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
        self._active_result: CrawlRunResult | None = None
        self.current_started_at: datetime | None = None
        self.current_source: str | None = None
        self.current_sources: set[str] = set()
        self.total_sources = 0
        self.completed_sources = 0
        self._task: asyncio.Task[CrawlRunResult] | None = None
        self.current_trigger: str | None = None
        self.last_trigger: str | None = None

    @property
    def running(self) -> bool:
        return self._lock.locked() or (self._task is not None and not self._task.done())

    def start(
        self, source_code: str | None = None, trigger: str = "manual"
    ) -> asyncio.Task[CrawlRunResult]:
        if self.running:
            raise CrawlerAlreadyRunning("crawler is already running")
        # A task is observable as running immediately after create_task(). Set the
        # trigger before yielding to it so status consumers never see a running
        # crawler with an empty trigger source.
        self.current_trigger = trigger
        self._task = asyncio.create_task(self.run(source_code=source_code, trigger=trigger))
        self._task.add_done_callback(self._log_task_result)
        log_event(logger, logging.INFO, "crawler_triggered", trigger_source=trigger)
        return self._task

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
        result = self._active_result if self.running and self._active_result else self.last_result
        if result is None and self._status_file.exists():
            try:
                saved = json.loads(self._status_file.read_text(encoding="utf-8"))
                if self.running:
                    saved.update(self._status_fields())
                return saved
            except (OSError, ValueError, TypeError):
                logger.warning("could not read persisted crawler status", exc_info=True)
        return {
            **self._status_fields(),
            "last_run": result.finished_at if result else None,
            "last_duration": result.duration_seconds if result else None,
            "new_count": result.new_count if result else 0,
            "updated_count": result.updated_count if result else 0,
            "unchanged_count": result.unchanged_count if result else 0,
            "source_results": [asdict(item) for item in result.source_results] if result else [],
        }

    def _status_fields(self) -> dict[str, Any]:
        result = self.last_result
        return {
            "running": self.running,
            "status": "running" if self.running else (result.status if result else "idle"),
            "current_started_at": self.current_started_at,
            "current_source": self.current_source,
            "current_sources": sorted(self.current_sources),
            "completed_sources": self.completed_sources,
            "total_sources": self.total_sources,
            "trigger_source": self.current_trigger or self.last_trigger,
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

    async def run(
        self, source_code: str | None = None, bootstrap: bool = False, trigger: str = "manual"
    ) -> CrawlRunResult:
        if self._lock.locked():
            raise CrawlerAlreadyRunning("crawler is already running")
        async with self._lock:
            self._acquire_file_lock()
            self.current_started_at = utcnow()
            result = CrawlRunResult(started_at=self.current_started_at, trigger=trigger)
            log_event(logger, logging.INFO, "crawler_started", trigger_source=trigger)
            self._active_result = result
            self.current_trigger = trigger
            try:
                init_db()
                configs = load_yaml("sources.yaml").get("sources", [])
                if source_code:
                    configs = [item for item in configs if item.get("code") == source_code]
                    if not configs:
                        raise ValueError(f"Unknown source: {source_code}")
                skipped_configs = [item for item in configs if not item.get("enabled", True)]
                configs = [item for item in configs if item.get("enabled", True)]
                self.total_sources = len(configs) + len(skipped_configs)
                self.completed_sources = len(skipped_configs)
                with SessionLocal() as db:
                    self._sync_sources(db, load_yaml("sources.yaml").get("sources", []))
                concurrency = max(
                    1, int(load_yaml("settings.yaml").get("crawler", {}).get("source_concurrency", 2))
                )
                semaphore = asyncio.Semaphore(concurrency)

                result.source_results = [
                    SourceRunResult(source=str(config["code"]), status="skipped")
                    for config in skipped_configs
                ] + [
                    SourceRunResult(source=str(config["code"])) for config in configs
                ]

                async def run_limited(index: int, config: dict[str, Any]) -> SourceRunResult:
                    async with semaphore:
                        code = str(config["code"])
                        self.current_source = code
                        self.current_sources.add(code)
                        try:
                            source_result = await self._run_source(config, bootstrap)
                            result.source_results[len(skipped_configs) + index] = source_result
                            self.completed_sources += 1
                            return source_result
                        finally:
                            self.current_sources.discard(code)
                            if self.current_source == code:
                                self.current_source = next(iter(self.current_sources), None)

                # gather preserves the config ordering, making status and reports stable.
                await asyncio.gather(
                    *(run_limited(index, config) for index, config in enumerate(configs))
                )
                for source_result in result.source_results:
                    result.new_count += source_result.new_count
                    result.updated_count += source_result.updated_count
                    result.unchanged_count += source_result.unchanged_count
                attempted = [item for item in result.source_results if item.status != "skipped"]
                failures = [item for item in attempted if item.status == "failure"]
                partials = [item for item in attempted if item.status == "partial_failure"]
                result.status = "failure" if failures and len(failures) == len(attempted) else (
                    "partial_failure" if failures or partials else "success"
                )
            except Exception:
                result.status = "failure"
                raise
            finally:
                result.finished_at = utcnow()
                self.last_result = result
                self.last_trigger = trigger
                self._active_result = None
                self.current_started_at = None
                self.current_trigger = None
                self.current_source = None
                self.current_sources.clear()
                self._status_file.parent.mkdir(parents=True, exist_ok=True)
                persisted = {
                    "running": False,
                    "status": result.status,
                    "current_started_at": None,
                    "current_source": None,
                    "current_sources": [],
                    "trigger_source": trigger,
                    "completed_sources": self.completed_sources,
                    "total_sources": self.total_sources,
                    "last_run": result.finished_at,
                    "last_duration": result.duration_seconds,
                    "new_count": result.new_count,
                    "updated_count": result.updated_count,
                    "unchanged_count": result.unchanged_count,
                    "source_results": [asdict(item) for item in result.source_results],
                }
                self._status_file.write_text(
                    json.dumps(persisted, ensure_ascii=False, default=str, indent=2),
                    encoding="utf-8",
                )
                self._lock_file.unlink(missing_ok=True)
                log_event(
                    logger, logging.INFO, "crawler_finished", trigger_source=trigger,
                    duration_seconds=result.duration_seconds or 0, status=result.status,
                    new_count=result.new_count, updated_count=result.updated_count,
                    unchanged_count=result.unchanged_count,
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
        run_result = SourceRunResult(source=code, status="running")
        adapter = build_source(config)
        log_event(logger, logging.INFO, "source_started", source=code)
        with SessionLocal() as db:
            db_source = db.scalar(select(Source).where(Source.code == code))
            assert db_source is not None
            db_source.last_checked_at = utcnow()
            db.commit()
            try:
                list_started = time.perf_counter()
                items = await adapter.fetch_list()
                run_result.list_duration_seconds = round(time.perf_counter() - list_started, 3)
                run_result.fetched = len(items)
                log_event(logger, logging.INFO, "source_list_fetched", source=code, status="success")
                for item in items:
                    try:
                        existing = self._find_unchanged_list_item(db, db_source, item)
                        if existing is not None:
                            self._mark_seen_without_detail(db, existing, db_source, item.url)
                            run_result.detail_skipped += 1
                            run_result.unchanged_count += 1
                            continue
                        detail_started = time.perf_counter()
                        detail = await adapter.fetch_detail(item)
                        run_result.detail_duration_seconds += time.perf_counter() - detail_started
                        run_result.detail_fetched += 1
                        persist_started = time.perf_counter()
                        state = self._persist_candidate(db, db_source, detail, bootstrap)
                        run_result.parse_db_duration_seconds += time.perf_counter() - persist_started
                        if state == "NEW":
                            run_result.new_count += 1
                        elif state == "UPDATED":
                            run_result.updated_count += 1
                        else:
                            run_result.unchanged_count += 1
                    except Exception as exc:  # one bad notice must not stop a source
                        message = f"{item.url}: {type(exc).__name__}: {exc}"
                        run_result.errors.append(message)
                        log_event(logger, logging.WARNING, "detail_fetch_failed", source=code, error_type=type(exc).__name__, error=message)
                        db.rollback()
                db_source.last_success_at = utcnow()
                if run_result.errors:
                    db_source.last_error = " | ".join(run_result.errors)
                    db_source.consecutive_errors += 1
                else:
                    db_source.last_error = None
                    db_source.consecutive_errors = 0
                run_result.status = "partial_failure" if run_result.errors else "success"
            except LoginExpiredError:
                db_source.last_error = "OA_LOGIN_EXPIRED"
                db_source.consecutive_errors += 1
                run_result.errors.append("OA_LOGIN_EXPIRED")
                log_event(logger, logging.ERROR, "source_failed", source=code, error_type="LoginExpiredError", error="OA_LOGIN_EXPIRED")
                run_result.status = "failure"
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                db_source.last_error = message
                db_source.consecutive_errors += 1
                run_result.errors.append(message)
                log_event(logger, logging.ERROR, "source_failed", source=code, error_type=type(exc).__name__, error=message)
                run_result.status = "failure"
            finally:
                run_result.detail_duration_seconds = round(run_result.detail_duration_seconds, 3)
                run_result.parse_db_duration_seconds = round(run_result.parse_db_duration_seconds, 3)
                db.commit()
                await adapter.close()
        log_event(
            logger, logging.INFO, "source_finished", source=code, status=run_result.status,
            duration_seconds=round(run_result.list_duration_seconds + run_result.detail_duration_seconds + run_result.parse_db_duration_seconds, 3),
            new_count=run_result.new_count, updated_count=run_result.updated_count,
            unchanged_count=run_result.unchanged_count,
        )
        return run_result

    @staticmethod
    def _find_unchanged_list_item(
        db: Session, source: Source, item: NoticeCandidate
    ) -> NoticeSourceRelation | None:
        """Return an existing relation only when list-page metadata is unchanged.

        List pages are intentionally the cheap change detector.  A title, publish
        date, or publisher change is treated as suspicious and proceeds to detail
        parsing, preserving the existing content-hash update semantics.
        """
        relation = db.scalar(
            select(NoticeSourceRelation).where(
                NoticeSourceRelation.source_id == source.id,
                NoticeSourceRelation.source_url == item.url,
            )
        )
        if relation is None:
            return None
        notice = relation.notice
        if (
            notice.title == item.title
            and notice.publish_date == item.publish_date
            and notice.publisher == item.publisher
        ):
            return relation
        return None

    @staticmethod
    def _mark_seen_without_detail(
        db: Session, relation: NoticeSourceRelation, source: Source, source_url: str) -> None:
        now = utcnow()
        relation.last_seen_at = now
        relation.notice.last_seen_at = now
        # The explicit source/url parameters document the identity that was
        # checked and guard against accidental cross-source relation reuse.
        assert relation.source_id == source.id and relation.source_url == source_url
        db.commit()

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
