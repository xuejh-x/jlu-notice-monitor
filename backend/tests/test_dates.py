from datetime import date

from app.services.dates import deadline_metadata, extract_dates, parse_date


def test_parse_multiple_date_formats() -> None:
    assert parse_date("2026年09月10日") == date(2026, 9, 10)
    assert parse_date("2026-09-10") == date(2026, 9, 10)
    assert parse_date("9月10日", 2026) == date(2026, 9, 10)


def test_context_aware_deadline_and_event_extraction() -> None:
    text = "通知发布于2026年8月20日。报名截止：2026年9月10日。比赛时间：2026年9月20日。"
    result = extract_dates(text, date(2026, 8, 20))
    assert result.registration_deadline == date(2026, 9, 10)
    assert result.event_start == date(2026, 9, 20)


def test_deadline_status() -> None:
    assert deadline_metadata(date(2026, 9, 1), date(2026, 8, 29)) == ("urgent", 3)
    assert deadline_metadata(date(2026, 8, 29), date(2026, 8, 29)) == ("today", 0)
    assert deadline_metadata(date(2026, 8, 28), date(2026, 8, 29))[0] == "expired"

