from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from src.storage.schemas import CATEGORY_SLUGS, EventDTO

logger = logging.getLogger(__name__)

YANDEX_CITY_PATH = {
    "moscow": "moscow",
    "spb": "saint-petersburg",
    "novosibirsk": "novosibirsk",
    "yekaterinburg": "yekaterinburg",
    "kazan": "kazan",
    "nizhny_novgorod": "nizhny-novgorod",
    "chelyabinsk": "chelyabinsk",
    "samara": "samara",
    "omsk": "omsk",
    "rostov_on_don": "rostov-on-don",
    "ufa": "ufa",
    "krasnoyarsk": "krasnoyarsk",
    "voronezh": "voronezh",
    "perm": "perm",
    "volgograd": "volgograd",
}

YANDEX_CATEGORY_PATH = {
    "concerts": "concert",
    "exhibitions": "art",
    "theater": "theatre",
    "sport": "sport",
    "education": "education",
    "other": "entertainment",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://yandex.ru/",
}


class YandexAfishaScraper:
    slug = "yandex_afisha"
    name = "Yandex Afisha"
    base_url = "https://afisha.yandex.ru"
    last_error: str | None = None

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        self.last_error = None
        city_path = YANDEX_CITY_PATH.get(city_slug)
        if not city_path:
            return []

        events: list[EventDTO] = []
        seen_urls: set[str] = set()

        try:
            async with httpx.AsyncClient(
                timeout=12.0,
                headers=BROWSER_HEADERS,
                follow_redirects=True,
            ) as client:
                for category_slug, rubric_path in YANDEX_CATEGORY_PATH.items():
                    url = f"{self.base_url}/{city_path}/{rubric_path}"
                    page_events, error = await self._fetch_page(client, url, city_slug, category_slug)
                    if error and not events:
                        self.last_error = error
                    for event in page_events:
                        key = str(event.source_url)
                        if key in seen_urls:
                            continue
                        seen_urls.add(key)
                        events.append(event)
                    await asyncio.sleep(1.0)
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("Yandex Afisha fetch failed for %s: %s", city_slug, exc)
            return events

        if not events and self.last_error is None:
            self.last_error = "no events parsed from category pages"
        return events

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        city_slug: str,
        category_slug: str,
    ) -> tuple[list[EventDTO], str | None]:
        try:
            response = await client.get(url)
        except Exception as exc:
            return [], f"{url}: {exc}"

        if response.status_code == 403:
            return [], (
                "Yandex Afisha blocked the request (403 captcha). "
                "Public HTML scraping is unavailable from this server; "
                "use KudaGo or deploy sync on a non-blocked host."
            )

        try:
            response.raise_for_status()
        except Exception as exc:
            return [], f"{url}: {exc}"

        if "smart-captcha" in response.text:
            return [], "Yandex Afisha returned captcha page"

        return self._parse_html(response.text, city_slug, category_slug), None

    def _parse_html(self, html: str, city_slug: str, category_slug: str) -> list[EventDTO]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("[data-event-card]")
        events: list[EventDTO] = []
        for card in cards:
            title = (card.get("data-title") or "").strip()
            source_url = card.get("data-url")
            start_at_text = card.get("data-start-at")
            venue = (card.get("data-venue") or "").strip() or None
            raw_category = (card.get("data-category") or category_slug).strip() or category_slug
            price_text = (card.get("data-price") or "").strip() or None
            image_url = (card.get("data-image-url") or "").strip() or None

            if not title or not source_url or not start_at_text:
                continue

            mapped_category = raw_category if raw_category in CATEGORY_SLUGS else category_slug
            if mapped_category not in CATEGORY_SLUGS:
                mapped_category = "other"

            try:
                start_at = datetime.fromisoformat(start_at_text.replace("Z", "+00:00")).astimezone(UTC)
                dto = EventDTO(
                    external_id=None,
                    source_url=source_url,
                    source_slug=self.slug,
                    title=title,
                    description=(card.get("data-description") or "").strip() or None,
                    category_slug=mapped_category,  # type: ignore[arg-type]
                    city_slug=city_slug,
                    venue=venue,
                    start_at=start_at,
                    end_at=None,
                    price_type="unknown" if not price_text else "paid",
                    price_text=price_text,
                    is_online=False,
                    image_url=image_url,
                )
            except Exception:
                continue
            events.append(dto)
        return events
