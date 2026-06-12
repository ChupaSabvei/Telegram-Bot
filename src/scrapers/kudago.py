from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from src.storage.schemas import CATEGORY_SLUGS, EventDTO

KUDAGO_CITY_MAP = {
    "moscow": "msk",
    "spb": "spb",
    "novosibirsk": "nsk",
    "yekaterinburg": "ekb",
    "kazan": "kzn",
    "nizhny_novgorod": "nn",
    "chelyabinsk": "chl",
    "samara": "smr",
    "omsk": "omsk",
    "rostov_on_don": "rnd",
    "ufa": "ufa",
    "krasnoyarsk": "krs",
    "voronezh": "vrn",
    "perm": "perm",
    "volgograd": "vlg",
}

CATEGORY_MAP = {
    "concert": "concerts",
    "exhibition": "exhibitions",
    "theater": "theater",
    "sport": "sport",
    "education": "education",
}


class KudaGoScraper:
    slug = "kudago"
    name = "KudaGo API"
    base_url = "https://kudago.com/public-api/v1.4/events/"

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        location = KUDAGO_CITY_MAP.get(city_slug)
        if not location:
            return []

        now = datetime.now(tz=UTC)
        params = {
            "location": location,
            "expand": "place",
            "fields": "id,title,description,dates,place,price,is_free,site_url,categories,images",
            "actual_since": int(now.timestamp()),
            "actual_until": int((now + timedelta(days=30)).timestamp()),
            "page_size": 100,
        }
        headers = {"User-Agent": "TelegramEventBot/1.0"}

        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []

        items: list[EventDTO] = []
        for raw in payload.get("results", []):
            place = raw.get("place") or {}
            venue = place.get("title")
            if not venue:
                continue

            dates = raw.get("dates") or []
            if not dates:
                continue
            start_ts = dates[0].get("start")
            if not start_ts:
                continue

            title = (raw.get("title") or "").strip()
            source_url = raw.get("site_url")
            if not title or not source_url:
                continue

            source_category = (raw.get("categories") or ["other"])[0]
            category_slug = CATEGORY_MAP.get(source_category, "other")
            if category_slug not in CATEGORY_SLUGS:
                category_slug = "other"

            price_text = raw.get("price")
            is_free = bool(raw.get("is_free"))
            price_type = "free" if is_free else "paid" if price_text else "unknown"
            image_url = None
            images = raw.get("images") or []
            if images:
                image_url = images[0].get("image")

            try:
                dto = EventDTO(
                    external_id=str(raw.get("id")),
                    source_url=source_url,
                    source_slug=self.slug,
                    title=title,
                    description=raw.get("description"),
                    category_slug=category_slug,
                    city_slug=city_slug,
                    venue=venue,
                    start_at=datetime.fromtimestamp(start_ts, tz=UTC),
                    end_at=None,
                    price_type=price_type,
                    price_text=price_text,
                    is_online=False,
                    image_url=image_url,
                )
            except Exception:
                continue
            items.append(dto)
        return items
