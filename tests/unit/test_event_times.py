from __future__ import annotations

from datetime import UTC, date, datetime

from src.scrapers.event_dates import combine_date_and_time, extract_iso_datetimes, pick_next_session, pick_session_for_date
from src.storage.event_times import event_in_date_range, resolve_display_start


def test_combine_date_and_time_accepts_iso_date() -> None:
    combined = combine_date_and_time("2026-06-16", "21:00")
    assert combined is not None
    assert combined.astimezone(UTC).hour == 18  # 21:00 MSK


def test_pick_next_session_uses_earliest_future() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    sessions = [
        datetime(2026, 6, 19, 15, 30, tzinfo=UTC),
        datetime(2026, 6, 18, 17, 0, tzinfo=UTC),
    ]
    assert pick_next_session(sessions, now=now) == sessions[1]


def test_pick_session_for_date() -> None:
    sessions = [
        datetime(2026, 6, 15, 14, 0, tzinfo=UTC),
        datetime(2026, 6, 20, 14, 0, tzinfo=UTC),
    ]
    picked = pick_session_for_date(sessions, date(2026, 6, 15))
    assert picked == sessions[0]


class _Event:
    def __init__(self, start_at: datetime, session_starts_at: list[str] | None = None, confirmed: bool = True):
        self.start_at = start_at
        self.session_starts_at = session_starts_at or []
        self.start_at_confirmed = confirmed


def test_resolve_display_start_prefers_selected_day_session() -> None:
    event = _Event(
        start_at=datetime(2026, 6, 19, 15, 30, tzinfo=UTC),
        session_starts_at=[
            "2026-06-18T20:00:00+03:00",
            "2026-06-19T18:30:00+03:00",
            "2026-06-19T21:30:00+03:00",
        ],
    )
    assert resolve_display_start(event) == datetime(2026, 6, 18, 17, 0, tzinfo=UTC)
    assert resolve_display_start(event, date(2026, 6, 19)) == datetime(2026, 6, 19, 15, 30, tzinfo=UTC)


def test_event_in_date_range_uses_any_session() -> None:
    from src.scrapers.event_dates import selected_date_range_utc

    event = _Event(
        start_at=datetime(2026, 6, 19, 15, 30, tzinfo=UTC),
        session_starts_at=["2026-06-15T17:00:00+03:00"],
    )
    start, end = selected_date_range_utc(date(2026, 6, 15))
    assert event_in_date_range(event, start, end)
