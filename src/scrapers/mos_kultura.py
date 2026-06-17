from __future__ import annotations

from src.scrapers.html_utils import fetch_html, parse_generic_cards, parse_json_ld_events
from src.storage.schemas import EventDTO

MOSCOW_ONLY = ("moscow",)


class MosKulturaScraper:
    slug = "mos_kultura"
    name = "Культура Москвы"
    base_url = "https://www.mos.ru"
    url = "https://www.mos.ru/kultura/"
    supported_cities = MOSCOW_ONLY
    last_error: str | None = None

    @staticmethod
    def parse_html(html: str, city_slug: str) -> list[EventDTO]:
        events = parse_json_ld_events(
            html,
            source_slug="mos_kultura",
            city_slug=city_slug,
            base_url=MosKulturaScraper.base_url,
            fallback_category="other",
        )
        if events:
            return events
        return parse_generic_cards(
            html,
            source_slug="mos_kultura",
            city_slug=city_slug,
            base_url=MosKulturaScraper.base_url,
            card_selector=".event-card, article, .news-item",
            fallback_category="other",
        )

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        self.last_error = None
        if city_slug not in MOSCOW_ONLY:
            return []
        html, error = await fetch_html(self.url, headers={"Referer": self.base_url})
        if html is None:
            self.last_error = error
            return []
        events = self.parse_html(html, city_slug)
        if not events:
            self.last_error = "no events parsed from page"
        return events
