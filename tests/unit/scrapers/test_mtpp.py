from __future__ import annotations

from src.scrapers.mtpp import MtppScraper


def test_mtpp_parse_html(mtpp_html: str) -> None:
    events = MtppScraper.parse_html(mtpp_html, "moscow")
    assert len(events) == 1
    event = events[0]
    assert event.source_slug == "mtpp"
    assert event.activity_slug == "culture"
    assert "мтпп" in event.title.lower()


def test_mtpp_city_locked() -> None:
    assert MtppScraper.supported_cities == ("moscow",)
