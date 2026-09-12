from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import re
import secrets
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Notice,
    NotificationDelivery,
    NotificationEvent,
    NotificationPreference,
    Source,
    UserState,
)

WINDOWS_CHANNEL = "WINDOWS_NATIVE"
MAX_DELIVERY_ATTEMPTS = 3
STALE_CLAIM_AFTER = timedelta(minutes=5)
INTERNAL_ROUTE = re.compile(r"^/(?:notices/[1-9]\d*|notices|deadlines|sources)$")


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def local_now() -> datetime:
    return datetime.now().astimezone()


def ensure_preferences(db: Session) -> NotificationPreference:
    preferences = db.get(NotificationPreference, 1)
    if preferences is None:
        preferences = NotificationPreference(id=1)
        db.add(preferences)
        db.flush()
    return preferences


def parse_lead_days(value: str) -> tuple[int, ...]:
    parsed = {int(item) for item in value.split(",") if item.strip().isdigit()}
    return tuple(sorted((item for item in parsed if 0 <= item <= 30), reverse=True))


def _parse_clock(value: str) -> time:
    return time.fromisoformat(value)


def _quiet_available_at(preferences: NotificationPreference, current: datetime) -> datetime:
    """Return a naive UTC availability timestamp for a local aware instant."""

    start = _parse_clock(preferences.quiet_start)
    end = _parse_clock(preferences.quiet_end)
    wall = current.timetz().replace(tzinfo=None)
    if start == end:
        return current.astimezone(UTC).replace(tzinfo=None)
    overnight = start > end
    quiet = (wall >= start or wall < end) if overnight else start <= wall < end
    if not quiet:
        return current.astimezone(UTC).replace(tzinfo=None)
    end_date = current.date()
    if overnight and wall >= start:
        end_date += timedelta(days=1)
    local_end = datetime.combine(end_date, end, tzinfo=current.tzinfo)
    return local_end.astimezone(UTC).replace(tzinfo=None)


def _desktop_notifications_enabled() -> bool:
    # Standalone is the isolated local-development equivalent of Desktop.
    # Cloud workers must never create or retain personal notification state.
    return get_settings().effective_deployment_role != "cloud"


def _create_event(
    db: Session,
    *,
    dedupe_key: str,
    event_type: str,
    title: str,
    body: str,
    severity: str = "info",
    notice_id: int | None = None,
    source_id: int | None = None,
    route: str | None = None,
    event_local_date: date | None = None,
    current_local: datetime | None = None,
) -> NotificationEvent | None:
    if route is not None and not INTERNAL_ROUTE.fullmatch(route):
        raise ValueError("notification route is not an allowed internal route")
    preferences = ensure_preferences(db)
    current_local = current_local or local_now()
    values = {
        "dedupe_key": dedupe_key,
        "event_type": event_type,
        "notice_id": notice_id,
        "source_id": source_id,
        "severity": severity,
        "title": title[:200],
        "body": body[:500],
        "route": route,
        "local_date": event_local_date.isoformat() if event_local_date else None,
        "available_at": _quiet_available_at(preferences, current_local),
        "created_at": utcnow(),
    }
    result = db.execute(
        sqlite_insert(NotificationEvent)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    if result.rowcount == 0:
        return None
    return db.scalar(select(NotificationEvent).where(NotificationEvent.dedupe_key == dedupe_key))


def record_notice_event(
    db: Session,
    notice: Notice,
    state: str,
    *,
    old_deadline: date | None = None,
    current_local: datetime | None = None,
) -> list[NotificationEvent]:
    if not _desktop_notifications_enabled():
        return []
    preferences = ensure_preferences(db)
    if not preferences.enabled:
        return []
    created: list[NotificationEvent] = []
    if state == "NEW":
        if preferences.important_notice_enabled and notice.importance_score >= preferences.minimum_importance:
            event = _create_event(
                db,
                dedupe_key=f"IMPORTANT_NOTICE:{notice.id}",
                event_type="IMPORTANT_NOTICE",
                title="发现重要通知",
                body=notice.title,
                severity="warning",
                notice_id=notice.id,
                route=f"/notices/{notice.id}",
                current_local=current_local,
            )
        elif preferences.new_notice_enabled:
            event = _create_event(
                db,
                dedupe_key=f"NEW_NOTICE:{notice.id}",
                event_type="NEW_NOTICE",
                title="收到新通知",
                body=notice.title,
                notice_id=notice.id,
                route=f"/notices/{notice.id}",
                current_local=current_local,
            )
        else:
            event = None
        if event is not None:
            created.append(event)
    if state == "UPDATED" and preferences.deadline_enabled and old_deadline != notice.registration_deadline:
        old_value = old_deadline.isoformat() if old_deadline else "none"
        new_value = notice.registration_deadline.isoformat() if notice.registration_deadline else "none"
        body = (
            f"截止日期已从 {old_value} 调整为 {new_value}。"
            if old_deadline and notice.registration_deadline
            else f"截止日期已更新为 {new_value}。"
        )
        event = _create_event(
            db,
            dedupe_key=f"DEADLINE_CHANGED:{notice.id}:{old_value}:{new_value}",
            event_type="DEADLINE_CHANGED",
            title="通知截止日期有变化",
            body=body,
            severity="warning",
            notice_id=notice.id,
            route=f"/notices/{notice.id}",
            current_local=current_local,
        )
        if event is not None:
            created.append(event)
    return created


def record_source_health_transition(
    db: Session,
    source: Source,
    previous_health: str,
    *,
    current_local: datetime | None = None,
) -> NotificationEvent | None:
    if not _desktop_notifications_enabled():
        return None
    preferences = ensure_preferences(db)
    if not preferences.enabled or not preferences.source_health_enabled:
        return None
    if source.health_state == previous_health or source.health_state == "healthy":
        return None
    checked = source.last_checked_at or utcnow()
    fingerprint = checked.isoformat(timespec="microseconds")
    if source.health_state == "cloud_unconfigured" or source.last_error_code == "PUBLIC_FEED_NOT_CONFIGURED":
        event_type, severity = "SOURCE_ERROR", "info"
        title, body = "云端来源尚未配置", f"{source.name} 暂无云端地址，不影响本地数据。"
    elif source.health_state == "needs_reauth":
        event_type, severity = "SOURCE_AUTH_REQUIRED", "warning"
        title, body = "来源需要重新登录", f"{source.name} 的登录状态已失效，请前往来源设置处理。"
    else:
        event_type, severity = "SOURCE_ERROR", "error"
        title, body = "来源检查失败", f"{source.name} 暂时无法更新，请稍后重试。"
    return _create_event(
        db,
        dedupe_key=f"{event_type}:{source.id}:{source.health_state}:{fingerprint}",
        event_type=event_type,
        title=title,
        body=body,
        severity=severity,
        source_id=source.id,
        route="/sources",
        current_local=current_local,
    )


def generate_scheduled_events(
    db: Session, *, current_local: datetime | None = None
) -> list[NotificationEvent]:
    if not _desktop_notifications_enabled():
        return []
    current_local = current_local or local_now()
    preferences = ensure_preferences(db)
    if not preferences.enabled:
        return []
    created: list[NotificationEvent] = []
    today = current_local.date()
    if preferences.deadline_enabled:
        lead_days = parse_lead_days(preferences.deadline_lead_days)
        if lead_days:
            targets = [today + timedelta(days=days) for days in lead_days]
            notices = db.scalars(
                select(Notice).where(
                    Notice.registration_deadline.in_(targets), Notice.status == "active"
                )
            ).all()
            for notice in notices:
                assert notice.registration_deadline is not None
                days = (notice.registration_deadline - today).days
                event = _create_event(
                    db,
                    dedupe_key=(
                        f"DEADLINE_APPROACHING:{notice.id}:"
                        f"{notice.registration_deadline.isoformat()}:{days}"
                    ),
                    event_type="DEADLINE_APPROACHING",
                    title=f"{notice.title[:150]}即将截止",
                    body=f"还有 {days} 天截止，点击查看详情。" if days else "今天截止，点击查看详情。",
                    severity="warning",
                    notice_id=notice.id,
                    route=f"/notices/{notice.id}",
                    event_local_date=today,
                    current_local=current_local,
                )
                if event is not None:
                    created.append(event)
    summary_clock = _parse_clock(preferences.daily_summary_time)
    wall = current_local.timetz().replace(tzinfo=None)
    if preferences.daily_summary_enabled and wall >= summary_clock:
        start_local = datetime.combine(today, time.min, tzinfo=current_local.tzinfo)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
        end_utc = end_local.astimezone(UTC).replace(tzinfo=None)
        new_condition = (Notice.first_seen_at >= start_utc, Notice.first_seen_at < end_utc)
        new_count = db.scalar(select(func.count(Notice.id)).where(*new_condition)) or 0
        important_count = db.scalar(
            select(func.count(Notice.id)).where(
                *new_condition, Notice.importance_score >= preferences.minimum_importance
            )
        ) or 0
        max_lead = max(parse_lead_days(preferences.deadline_lead_days) or (7,))
        deadline_count = db.scalar(
            select(func.count(Notice.id)).where(
                Notice.registration_deadline >= today,
                Notice.registration_deadline <= today + timedelta(days=max_lead),
                Notice.status == "active",
            )
        ) or 0
        unread_count = db.scalar(
            select(func.count(Notice.id))
            .outerjoin(UserState, UserState.notice_id == Notice.id)
            .where(or_(UserState.id.is_(None), UserState.is_read.is_(False)))
        ) or 0
        event = _create_event(
            db,
            dedupe_key=f"DAILY_SUMMARY:{today.isoformat()}",
            event_type="DAILY_SUMMARY",
            title="Notice Hub 今日摘要",
            body=f"新增 {new_count} · 重要 {important_count} · 即将截止 {deadline_count} · 未读 {unread_count}",
            route="/notices",
            event_local_date=today,
            current_local=current_local,
        )
        if event is not None:
            created.append(event)
    return created


def _event_enabled(event_type: str, preferences: NotificationPreference) -> bool:
    if not preferences.enabled:
        return False
    return {
        "NEW_NOTICE": preferences.new_notice_enabled,
        "IMPORTANT_NOTICE": preferences.important_notice_enabled,
        "DEADLINE_APPROACHING": preferences.deadline_enabled,
        "DEADLINE_CHANGED": preferences.deadline_enabled,
        "SOURCE_AUTH_REQUIRED": preferences.source_health_enabled,
        "SOURCE_ERROR": preferences.source_health_enabled,
        "DAILY_SUMMARY": preferences.daily_summary_enabled,
    }.get(event_type, False)


def suppress_disabled_deliveries(db: Session) -> None:
    preferences = ensure_preferences(db)
    events = db.scalars(select(NotificationEvent)).all()
    for event in events:
        if _event_enabled(event.event_type, preferences):
            continue
        delivery = db.scalar(
            select(NotificationDelivery).where(
                NotificationDelivery.event_id == event.id,
                NotificationDelivery.channel == WINDOWS_CHANNEL,
            )
        )
        if delivery is None:
            db.add(
                NotificationDelivery(
                    event_id=event.id, channel=WINDOWS_CHANNEL, status="SUPPRESSED"
                )
            )
        elif delivery.status in {"PENDING", "FAILED"}:
            delivery.status = "SUPPRESSED"


def claim_delivery(db: Session, *, now: datetime | None = None) -> dict[str, Any] | None:
    now = now or utcnow()
    preferences = ensure_preferences(db)
    if not preferences.enabled:
        return None
    stale_before = now - STALE_CLAIM_AFTER
    for stale in db.scalars(
        select(NotificationDelivery).where(
            NotificationDelivery.status == "SENDING",
            NotificationDelivery.claimed_at < stale_before,
        )
    ).all():
        stale.status = "UNCERTAIN"
        stale.claim_token = None
        stale.last_error = "Delivery acknowledgement was interrupted; not retried to avoid duplication."
    db.flush()

    events = db.scalars(
        select(NotificationEvent)
        .where(NotificationEvent.available_at <= now)
        .order_by(NotificationEvent.created_at, NotificationEvent.id)
    ).all()
    for event in events:
        delivery = db.scalar(
            select(NotificationDelivery).where(
                NotificationDelivery.event_id == event.id,
                NotificationDelivery.channel == WINDOWS_CHANNEL,
            )
        )
        if not _event_enabled(event.event_type, preferences):
            if delivery is None:
                db.add(NotificationDelivery(event_id=event.id, channel=WINDOWS_CHANNEL, status="SUPPRESSED"))
            continue
        if delivery is None:
            delivery = NotificationDelivery(
                event_id=event.id,
                channel=WINDOWS_CHANNEL,
                status="PENDING",
                next_attempt_at=now,
            )
            db.add(delivery)
            db.flush()
        claimable = delivery.status == "PENDING" or (
            delivery.status == "FAILED"
            and delivery.attempt_count < MAX_DELIVERY_ATTEMPTS
            and (delivery.next_attempt_at is None or delivery.next_attempt_at <= now)
        )
        if not claimable:
            continue
        token = secrets.token_hex(16)
        delivery.status = "SENDING"
        delivery.claim_token = token
        delivery.claimed_at = now
        delivery.attempt_count += 1
        db.commit()
        return {
            "delivery_id": delivery.id,
            "claim_token": token,
            "event": serialize_event(event),
        }
    db.commit()
    return None


def complete_delivery(
    db: Session,
    delivery_id: int,
    claim_token: str,
    *,
    delivered: bool,
    error: str | None = None,
    now: datetime | None = None,
) -> NotificationDelivery:
    now = now or utcnow()
    delivery = db.get(NotificationDelivery, delivery_id)
    if delivery is None or delivery.claim_token != claim_token:
        raise LookupError("delivery claim not found")
    if delivery.status == "DELIVERED":
        return delivery
    if delivery.status != "SENDING":
        raise ValueError("delivery is not awaiting acknowledgement")
    delivery.claim_token = None
    if delivered:
        delivery.status = "DELIVERED"
        delivery.delivered_at = now
        delivery.last_error = None
    else:
        delivery.status = "FAILED"
        delivery.failed_at = now
        delivery.last_error = (error or "Native notification API rejected the request")[:500]
        delivery.next_attempt_at = now + timedelta(minutes=min(30, 2 ** delivery.attempt_count))
    db.commit()
    return delivery


def serialize_event(event: NotificationEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.event_type,
        "notice_id": event.notice_id,
        "source_id": event.source_id,
        "severity": event.severity,
        "title": event.title,
        "body": event.body,
        "route": event.route,
        "local_date": event.local_date,
        "read_at": event.read_at,
        "created_at": event.created_at,
    }
