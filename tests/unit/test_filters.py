from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.scrapers.runner import filter_event_window
from src.storage.schemas import EventDTO


def make_event(start_at: datetime, is_online: bool = False) -> EventDTO:
    return EventDTO(
        source_url="https://example.com/event",
        source_slug="kudago",
        title="Событие",
        description=None,
        category_slug="concerts",
        city_slug="moscow",
        venue="Клуб",
        start_at=start_at,
        end_at=None,
        price_type="unknown",
        price_text=None,
        is_online=False if not is_online else False,
    )


def test_filter_accepts_event_in_30_day_window() -> None:
    now = datetime.now(tz=UTC)
    event = make_event(now + timedelta(days=10))
    assert filter_event_window(event, now=now)


def test_filter_rejects_event_outside_30_day_window() -> None:
    now = datetime.now(tz=UTC)
    event = make_event(now + timedelta(days=40))
    assert not filter_event_window(event, now=now)


def test_filter_rejects_past_event() -> None:
    now = datetime.now(tz=UTC)
    event = make_event(now - timedelta(hours=1))
    assert not filter_event_window(event, now=now)
