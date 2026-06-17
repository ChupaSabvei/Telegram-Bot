from __future__ import annotations

import re

from src.scrapers.html_utils import fetch_html, parse_generic_cards, parse_json_ld_events
from src.storage.schemas import EventDTO

TIMEPAD_CITY_PATH = {
    "moscow": "moscow",
    "spb": "saint-petersburg",
}


class TimepadScraper:
    slug = "timepad"
    name = "Timepad Afisha"
    base_url = "https://afisha.timepad.ru"
    supported_cities = tuple(TIMEPAD_CITY_PATH.keys())
    last_error: str | None = None

    def city_url(self, city_slug: str) -> str | None:
        city_path = TIMEPAD_CITY_PATH.get(city_slug)
        if not city_path:
            return None
        return f"{self.base_url}/{city_path}"

    @staticmethod
    def _is_event_url(source_url: str) -> bool:
        lowered = source_url.lower()
        if "/collections/" in lowered:
            return False
        return bool(re.search(r"/\d{5,}", lowered) or "/event/" in lowered)

    @staticmethod
    def parse_html(html: str, city_slug: str) -> list[EventDTO]:
        events = parse_json_ld_events(
            html,
            source_slug="timepad",
            city_slug=city_slug,
            base_url=TimepadScraper.base_url,
            fallback_category="other",
        )
        if events:
            return [event for event in events if TimepadScraper._is_event_url(str(event.source_url))]
        parsed = parse_generic_cards(
            html,
            source_slug="timepad",
            city_slug=city_slug,
            base_url=TimepadScraper.base_url,
            card_selector='[data-test="event-item"], article, .event-item',
            fallback_category="other",
        )
        return [event for event in parsed if TimepadScraper._is_event_url(str(event.source_url))]
    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        self.last_error = None
        url = self.city_url(city_slug)
        if not url:
            return []
        html, error = await fetch_html(url, headers={"Referer": "https://timepad.ru/"})
        if html is None:
            self.last_error = error
            return []

        events = self.parse_html(html, city_slug)
        if not events:
            self.last_error = "no events parsed from city page"
        return events
