from __future__ import annotations

from src.scrapers.html_utils import fetch_html, parse_generic_cards
from src.storage.schemas import EventDTO

MOSCOW_ONLY = ("moscow",)


class TimeoutMskScraper:
    slug = "timeout_msk"
    name = "Time Out Москва"
    base_url = "https://www.timeout.ru"
    url = "https://www.timeout.ru/msk/all/week"
    supported_cities = MOSCOW_ONLY
    last_error: str | None = None

    @staticmethod
    def parse_html(html: str, city_slug: str) -> list[EventDTO]:
        return parse_generic_cards(
            html,
            source_slug="timeout_msk",
            city_slug=city_slug,
            base_url=TimeoutMskScraper.base_url,
            card_selector=".post-card, article, .content-list-item",
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
