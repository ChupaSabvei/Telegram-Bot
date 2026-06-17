from __future__ import annotations

from src.scrapers.timeout_msk import TimeoutMskScraper


def test_timeout_msk_parse_html(timeout_msk_html: str) -> None:
    events = TimeoutMskScraper.parse_html(timeout_msk_html, "moscow")
    assert len(events) == 1
    assert events[0].source_slug == "timeout_msk"
    assert events[0].title == "Time Out Event"


def test_timeout_city_locked() -> None:
    assert TimeoutMskScraper.supported_cities == ("moscow",)
