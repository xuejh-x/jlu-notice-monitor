from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class AttachmentData(BaseModel):
    filename: str
    url: str
    type: str


class NoticeCandidate(BaseModel):
    title: str
    url: str
    publish_date: date | None = None
    publisher: str | None = None
    content: str = ""
    attachments: list[AttachmentData] = Field(default_factory=list)
    section: str | None = None


class ExtractedDates(BaseModel):
    registration_start: date | None = None
    registration_deadline: date | None = None
    event_start: date | None = None
    event_end: date | None = None

