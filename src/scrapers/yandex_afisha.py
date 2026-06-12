from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from src.storage.schemas import EventDTO

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


class YandexAfishaScraper:
    slug = "yandex_afisha"
    name = "Yandex Afisha"
    base_url = "https://afisha.yandex.ru"

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        city_path = YANDEX_CITY_PATH.get(city_slug)
        if not city_path:
            return []
        url = f"{self.base_url}/{city_path}"
        headers = {"User-Agent": "TelegramEventBot/1.0"}
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except Exception:
            return []

        await asyncio.sleep(1.0)
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("[data-event-card]")
        events: list[EventDTO] = []
        for card in cards:
            title = (card.get("data-title") or "").strip()
            source_url = card.get("data-url")
            start_at_text = card.get("data-start-at")
            venue = (card.get("data-venue") or "").strip() or None
            category_slug = (card.get("data-category") or "other").strip() or "other"
            price_text = (card.get("data-price") or "").strip() or None
            image_url = (card.get("data-image-url") or "").strip() or None

            if not title or not source_url or not start_at_text:
                continue

            try:
                start_at = datetime.fromisoformat(start_at_text.replace("Z", "+00:00")).astimezone(
                    UTC
                )
                dto = EventDTO(
                    external_id=None,
                    source_url=source_url,
                    source_slug=self.slug,
                    title=title,
                    description=(card.get("data-description") or "").strip() or None,
                    category_slug=category_slug,  # type: ignore[arg-type]
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
