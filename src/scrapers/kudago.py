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
    "festival": "other",
    "party": "other",
    "cinema": "other",
    "quest": "other",
    "show": "concerts",
    "kids": "education",
}

KUDAGO_FETCH_CATEGORIES = tuple(CATEGORY_MAP.keys())
MAX_PAGES_PER_CATEGORY = 3
PAGE_SIZE = 100


def _pick_start_at(
    dates: list[dict],
    now: datetime,
    horizon: datetime,
) -> datetime | None:
    best: datetime | None = None
    for entry in dates:
        start_ts = entry.get("start")
        if not start_ts or start_ts <= 0:
            continue
        try:
            start_at = datetime.fromtimestamp(start_ts, tz=UTC)
        except (OSError, OverflowError, ValueError):
            continue
        if now < start_at <= horizon:
            if best is None or start_at < best:
                best = start_at
    return best


def _resolve_category_slug(raw: dict, fallback_source_category: str) -> str:
    source_category = (raw.get("categories") or [fallback_source_category])[0]
    category_slug = CATEGORY_MAP.get(source_category, CATEGORY_MAP.get(fallback_source_category, "other"))
    if category_slug not in CATEGORY_SLUGS:
        category_slug = "other"
    return category_slug


class KudaGoScraper:
    slug = "kudago"
    name = "KudaGo API"
    base_url = "https://kudago.com/public-api/v1.4/events/"

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        location = KUDAGO_CITY_MAP.get(city_slug)
        if not location:
            return []

        now = datetime.now(tz=UTC)
        horizon = now + timedelta(days=30)
        headers = {"User-Agent": "TelegramEventBot/1.0"}
        seen_ids: set[str] = set()
        items: list[EventDTO] = []

        try:
            async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
                for source_category in KUDAGO_FETCH_CATEGORIES:
                    page = 1
                    while page <= MAX_PAGES_PER_CATEGORY:
                        params = {
                            "location": location,
                            "categories": source_category,
                            "expand": "place",
                            "fields": (
                                "id,title,description,dates,place,price,is_free,"
                                "site_url,categories,images"
                            ),
                            "actual_since": int(now.timestamp()),
                            "actual_until": int(horizon.timestamp()),
                            "page_size": PAGE_SIZE,
                            "page": page,
                        }
                        response = await client.get(self.base_url, params=params)
                        response.raise_for_status()
                        payload = response.json()
                        results = payload.get("results", [])
                        if not results:
                            break

                        for raw in results:
                            external_id = str(raw.get("id"))
                            if external_id in seen_ids:
                                continue

                            place = raw.get("place") or {}
                            venue = (place.get("title") or "").strip()
                            if not venue:
                                continue

                            start_at = _pick_start_at(raw.get("dates") or [], now, horizon)
                            if start_at is None:
                                continue

                            title = (raw.get("title") or "").strip()
                            source_url = raw.get("site_url")
                            if not title or not source_url:
                                continue

                            category_slug = _resolve_category_slug(raw, source_category)
                            price_text = raw.get("price")
                            is_free = bool(raw.get("is_free"))
                            price_type = "free" if is_free else "paid" if price_text else "unknown"
                            image_url = None
                            images = raw.get("images") or []
                            if images:
                                image_url = images[0].get("image")

                            try:
                                dto = EventDTO(
                                    external_id=external_id,
                                    source_url=source_url,
                                    source_slug=self.slug,
                                    title=title,
                                    description=raw.get("description"),
                                    category_slug=category_slug,
                                    city_slug=city_slug,
                                    venue=venue,
                                    start_at=start_at,
                                    end_at=None,
                                    price_type=price_type,
                                    price_text=price_text,
                                    is_online=False,
                                    image_url=image_url,
                                )
                            except Exception:
                                continue

                            seen_ids.add(external_id)
                            items.append(dto)

                        if not payload.get("next"):
                            break
                        page += 1
        except Exception:
            return items

        return items
