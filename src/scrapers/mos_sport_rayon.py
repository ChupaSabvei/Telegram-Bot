from __future__ import annotations

from src.scrapers.html_utils import fetch_html, parse_generic_cards
from src.storage.schemas import EventDTO

MOSCOW_ONLY = ("moscow",)


class MosSportRayonScraper:
    slug = "mos_sport_rayon"
    name = "Мой спортивный район"
    base_url = "https://moysportrayon.sport.mos.ru"
    url = "https://moysportrayon.sport.mos.ru"
    supported_cities = MOSCOW_ONLY
    last_error: str | None = None

    @staticmethod
    def parse_html(html: str, city_slug: str) -> list[EventDTO]:
        events = parse_generic_cards(
            html,
            source_slug="mos_sport_rayon",
            city_slug=city_slug,
            base_url=MosSportRayonScraper.base_url,
            card_selector=".event-card, article, .schedule-item",
            fallback_category="sport",
        )
        for event in events:
            event.activity_slug = "sport"
            event.venue_format = "outdoor"
            event.price_type = "free"
        return events

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
