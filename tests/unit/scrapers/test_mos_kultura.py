from __future__ import annotations

from src.scrapers.mos_kultura import MosKulturaScraper


def test_mos_kultura_parse_html(mos_kultura_html: str) -> None:
    events = MosKulturaScraper.parse_html(mos_kultura_html, "moscow")
    assert len(events) == 1
    assert events[0].source_slug == "mos_kultura"
    assert "выставка" in events[0].title.lower()


def test_mos_kultura_city_locked() -> None:
    assert MosKulturaScraper.supported_cities == ("moscow",)
