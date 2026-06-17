from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from src.scrapers.event_dates import parse_utc_iso

MSK = timezone(timedelta(hours=3))


def test_parse_utc_iso_mts_event_time() -> None:
    parsed = parse_utc_iso("2026-07-08T16:00:00")
    assert parsed is not None
    assert parsed.astimezone(MSK).strftime("%H:%M") == "19:00"


def test_parse_utc_iso_standup_session() -> None:
    parsed = parse_utc_iso("2026-06-16T16:30:00")
    assert parsed is not None
    assert parsed.astimezone(MSK).strftime("%d.%m %H:%M") == "16.06 19:30"
