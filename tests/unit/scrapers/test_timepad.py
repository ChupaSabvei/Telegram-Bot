from __future__ import annotations

from src.scrapers.timepad import TimepadScraper


def test_timepad_parse_html(timepad_html: str) -> None:
    events = TimepadScraper.parse_html(timepad_html, "moscow")
    assert len(events) == 1
    event = events[0]
    assert event.title == "Timepad Event"
    assert event.source_slug == "timepad"
    assert event.city_slug == "moscow"
    assert event.price_amount_rub == 1200
    assert str(event.source_url) == "https://afisha.timepad.ru/event/1001"


def test_timepad_supports_all_project_cities() -> None:
    assert len(TimepadScraper.supported_cities) == 2
