from __future__ import annotations

from src.scrapers.mos_sport_rayon import MosSportRayonScraper


def test_mos_sport_rayon_parse_html(mos_sport_rayon_html: str) -> None:
    events = MosSportRayonScraper.parse_html(mos_sport_rayon_html, "moscow")
    assert len(events) == 1
    event = events[0]
    assert event.source_slug == "mos_sport_rayon"
    assert event.activity_slug == "sport"
    assert event.venue_format == "outdoor"
    assert event.price_type == "free"


def test_mos_sport_city_locked() -> None:
    assert MosSportRayonScraper.supported_cities == ("moscow",)
