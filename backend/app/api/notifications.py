from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import NotificationDelivery, NotificationEvent, NotificationPreference
from app.services.notifications import (
    WINDOWS_CHANNEL,
    claim_delivery,
    complete_delivery,
    ensure_preferences,
    generate_scheduled_events,
    serialize_event,
    suppress_disabled_deliveries,
    utcnow,
)

def require_local_notifications() -> None:
    if get_settings().effective_deployment_role == "cloud":
        raise HTTPException(status_code=404, detail="Notifications are available on Desktop only")


router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_local_notifications)],
)


class NotificationPreferencesUpdate(BaseModel):
    enabled: bool
    new_notice_enabled: bool
    important_notice_enabled: bool
    deadline_enabled: bool
    source_health_enabled: bool
    daily_summary_enabled: bool
    minimum_importance: int = Field(ge=0, le=100)
    deadline_lead_days: list[int] = Field(min_length=1, max_length=8)
    quiet_start: str
    quiet_end: str

    @field_validator("deadline_lead_days")
    @classmethod
    def validate_lead_days(cls, values: list[int]) -> list[int]:
        if any(isinstance(item, bool) or item < 0 or item > 30 for item in values):
            raise ValueError("deadline lead days must be integers from 0 to 30")
        return sorted(set(values), reverse=True)

    @field_validator("quiet_start", "quiet_end")
    @classmethod
    def validate_clock(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM") from exc
        return value


class DeliveryAcknowledgement(BaseModel):
    claim_token: str = Field(min_length=32, max_length=64)
    status: Literal["DELIVERED", "FAILED"]
    error: str | None = Field(default=None, max_length=500)


def _serialize_preferences(value: NotificationPreference) -> dict[str, object]:
    return {
        "enabled": value.enabled,
        "new_notice_enabled": value.new_notice_enabled,
        "important_notice_enabled": value.important_notice_enabled,
        "deadline_enabled": value.deadline_enabled,
        "source_health_enabled": value.source_health_enabled,
        "daily_summary_enabled": value.daily_summary_enabled,
        "minimum_importance": value.minimum_importance,
        "deadline_lead_days": [
            int(item) for item in value.deadline_lead_days.split(",") if item.strip().isdigit()
        ],
        "quiet_start": value.quiet_start,
        "quiet_end": value.quiet_end,
    }


@router.get("/preferences")
def get_notification_preferences(db: Session = Depends(get_db)) -> dict[str, object]:
    preferences = ensure_preferences(db)
    db.commit()
    return _serialize_preferences(preferences)


@router.patch("/preferences")
def update_notification_preferences(
    payload: NotificationPreferencesUpdate, db: Session = Depends(get_db)
) -> dict[str, object]:
    preferences = ensure_preferences(db)
    for field, value in payload.model_dump(exclude={"deadline_lead_days"}).items():
        setattr(preferences, field, value)
    preferences.deadline_lead_days = ",".join(str(item) for item in payload.deadline_lead_days)
    db.flush()
    suppress_disabled_deliveries(db)
    generate_scheduled_events(db)
    db.commit()
    return _serialize_preferences(preferences)


@router.get("")
def list_notification_events(
    limit: int = Query(8, ge=1, le=50), db: Session = Depends(get_db)
) -> dict[str, object]:
    events = db.scalars(
        select(NotificationEvent)
        .order_by(NotificationEvent.created_at.desc(), NotificationEvent.id.desc())
        .limit(limit)
    ).all()
    unread = db.scalar(
        select(func.count(NotificationEvent.id)).where(NotificationEvent.read_at.is_(None))
    ) or 0
    return {"items": [serialize_event(event) for event in events], "unread": unread}


@router.post("/generate")
def generate_notifications(db: Session = Depends(get_db)) -> dict[str, int]:
    events = generate_scheduled_events(db)
    db.commit()
    return {"created": len(events)}


@router.post("/claim")
def claim_notification(db: Session = Depends(get_db)) -> dict[str, object]:
    delivery = claim_delivery(db)
    return {"delivery": delivery}


@router.post("/deliveries/{delivery_id}/ack")
def acknowledge_delivery(
    delivery_id: int, payload: DeliveryAcknowledgement, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        delivery = complete_delivery(
            db,
            delivery_id,
            payload.claim_token,
            delivered=payload.status == "DELIVERED",
            error=payload.error,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Delivery claim not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "delivery_id": delivery.id,
        "channel": WINDOWS_CHANNEL,
        "status": delivery.status,
        "attempt_count": delivery.attempt_count,
    }


@router.post("/{event_id}/read")
def mark_notification_read(event_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    event = db.get(NotificationEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Notification event not found")
    if event.read_at is None:
        event.read_at = utcnow()
        db.commit()
    return {"event_id": event.id, "read_at": event.read_at}
