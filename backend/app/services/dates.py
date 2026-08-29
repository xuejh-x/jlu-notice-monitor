from __future__ import annotations

import re
from datetime import date, datetime

from app.schemas.notice import ExtractedDates

DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2})\s*[年./\-]\s*(?P<month>1[0-2]|0?[1-9])\s*[月./\-]\s*"
    r"(?P<day>3[01]|[12]\d|0?[1-9])\s*日?"
)
MONTH_DAY_PATTERN = re.compile(
    r"(?P<month>1[0-2]|0?[1-9])\s*月\s*(?P<day>3[01]|[12]\d|0?[1-9])\s*日"
)

DEADLINE_WORDS = ("截止", "报名截止", "申报截止", "提交截止", "截至")
REGISTRATION_WORDS = ("报名时间", "申报时间", "申请时间")
EVENT_WORDS = ("比赛时间", "活动时间", "竞赛时间", "举办时间", "考试时间", "培训时间")


def parse_date(value: str, reference_year: int | None = None) -> date | None:
    match = DATE_PATTERN.search(value)
    if match:
        try:
            return date(int(match["year"]), int(match["month"]), int(match["day"]))
        except ValueError:
            return None
    match = MONTH_DAY_PATTERN.search(value)
    if match and reference_year:
        try:
            return date(reference_year, int(match["month"]), int(match["day"]))
        except ValueError:
            return None
    return None


def _dates_near_keywords(text: str, keywords: tuple[str, ...], year: int) -> list[date]:
    results: list[date] = []
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text, re.IGNORECASE):
            window = text[match.start() : match.start() + 120]
            window = re.split(r"[。；;\n\r]", window, maxsplit=1)[0]
            for date_match in DATE_PATTERN.finditer(window):
                parsed = parse_date(date_match.group(0), year)
                if parsed:
                    results.append(parsed)
            if not results:
                for short_match in MONTH_DAY_PATTERN.finditer(window):
                    parsed = parse_date(short_match.group(0), year)
                    if parsed:
                        results.append(parsed)
    return results


def extract_dates(text: str, publish_date: date | None = None) -> ExtractedDates:
    reference_year = publish_date.year if publish_date else datetime.now().year
    deadline_dates = _dates_near_keywords(text, DEADLINE_WORDS, reference_year)
    registration_dates = _dates_near_keywords(text, REGISTRATION_WORDS, reference_year)
    event_dates = _dates_near_keywords(text, EVENT_WORDS, reference_year)
    return ExtractedDates(
        registration_start=registration_dates[0] if registration_dates else None,
        registration_deadline=deadline_dates[-1] if deadline_dates else (
            registration_dates[-1] if len(registration_dates) > 1 else None
        ),
        event_start=event_dates[0] if event_dates else None,
        event_end=event_dates[-1] if len(event_dates) > 1 else None,
    )


def deadline_metadata(deadline: date | None, today: date | None = None) -> tuple[str, int | None]:
    if deadline is None:
        return "unknown", None
    current = today or date.today()
    days = (deadline - current).days
    if days < 0:
        return "expired", days
    if days == 0:
        return "today", 0
    if days <= 3:
        return "urgent", days
    return "normal", days
