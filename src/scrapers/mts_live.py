from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.scrapers.event_dates import extract_iso_datetimes, parse_utc_iso, pick_next_session
from src.scrapers.html_utils import absolutize, fetch_html, map_category_from_text, parse_price
from src.storage.schemas import EventDTO

logger = logging.getLogger(__name__)

MTS_CITY_PATH = {
    "moscow": "moscow",
    "spb": "spb",
}

MAX_DETAIL_FETCHES = 200
DETAIL_CONCURRENCY = 6


class MtsLiveScraper:
    slug = "mts_live"
    name = "MTS Live"
    base_url = "https://live.mts.ru"
    supported_cities = tuple(MTS_CITY_PATH.keys())
    last_error: str | None = None

    def city_url(self, city_slug: str) -> str | None:
        city_path = MTS_CITY_PATH.get(city_slug)
        if not city_path:
            return None
        return f"{self.base_url}/{city_path}"

    @staticmethod
    def _normalize_announcement_url(base_url: str, href: str) -> str | None:
        href = (href or "").strip()
        if not href or "/announcements/" not in href:
            return None
        parsed = urlparse(href)
        path = parsed.path if parsed.scheme else href.split("?", 1)[0]
        if "/announcements/" not in path:
            return None
        return urljoin(base_url, href if parsed.scheme else path + (f"?{parsed.query}" if parsed.query else ""))

    @classmethod
    def collect_announcement_urls(cls, html: str, *, city_slug: str) -> list[str]:
        city_path = MTS_CITY_PATH.get(city_slug)
        if not city_path:
            return []
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        urls: list[str] = []
        for link in soup.select('a[href*="/announcements/"]'):
            href = link.get("href", "")
            if city_path not in href:
                continue
            source_url = cls._normalize_announcement_url(cls.base_url, href)
            if not source_url or source_url in seen:
                continue
            seen.add(source_url)
            urls.append(source_url)
        return urls

    @classmethod
    def parse_detail_html(cls, html: str, *, source_url: str, city_slug: str) -> EventDTO | None:
        soup = BeautifulSoup(html, "html.parser")
        script = soup.select_one("script#__NEXT_DATA__")
        if script is None or not script.string:
            return None
        try:
            payload = json.loads(script.string)
        except json.JSONDecodeError:
            return None
        details = (
            payload.get("props", {})
            .get("pageProps", {})
            .get("initialState", {})
            .get("Announcements", {})
            .get("announcementDetails")
        )
        if not isinstance(details, dict):
            return None

        title = str(details.get("title") or "").strip()
        if not title:
            return None

        sessions = extract_iso_datetimes(details, parser=parse_utc_iso)
        start_at = pick_next_session(sessions)
        if start_at is None:
            start_raw = details.get("eventClosestDateTime") or details.get("lastEventDateTime")
            start_at = parse_utc_iso(str(start_raw)) if start_raw else None
        if start_at is None:
            return None

        venue_data = details.get("venue") if isinstance(details.get("venue"), dict) else {}
        venue = str(venue_data.get("title") or "").strip() or None
        address = str(venue_data.get("address") or "").strip() or None

        category = map_category_from_text(str(details.get("category") or ""), "concerts")
        price_text = None
        price_type = "unknown"
        price_amount = None
        min_price = details.get("eventMinPrice")
        if isinstance(min_price, int | float):
            price_text = f"от {int(min_price)} ₽"
            price_type, price_amount = parse_price(price_text)

        canonical_url = absolutize(cls.base_url, str(details.get("url") or source_url))
        image_url = absolutize(cls.base_url, str(details.get("banner") or "")) if details.get("banner") else None
        description = str(details.get("description") or "").strip() or None
        if description:
            description = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)

        try:
            return EventDTO(
                external_id=str(details.get("id") or ""),
                source_url=canonical_url or source_url,
                source_slug="mts_live",
                title=title,
                description=description,
                category_slug=category,
                city_slug=city_slug,
                venue=venue,
                address=address,
                start_at=start_at,
                start_at_confirmed=True,
                session_starts_at=sessions,
                price_type=price_type,
                price_text=price_text,
                price_amount_rub=price_amount,
                image_url=image_url,
            )
        except Exception:
            return None

    @staticmethod
    def parse_html(html: str, city_slug: str) -> list[EventDTO]:
        return []

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        self.last_error = None
        url = self.city_url(city_slug)
        if not url:
            return []
        html, error = await fetch_html(url, headers={"Referer": self.base_url})
        if html is None:
            self.last_error = error
            return []

        announcement_urls = self.collect_announcement_urls(html, city_slug=city_slug)[:MAX_DETAIL_FETCHES]
        if not announcement_urls:
            self.last_error = "no announcement links found on city page"
            return []

        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def fetch_detail(source_url: str) -> EventDTO | None:
            async with semaphore:
                detail_html, detail_error = await fetch_html(
                    source_url,
                    timeout=90.0,
                    headers={"Referer": self.base_url},
                )
                if detail_html is None:
                    logger.debug("MTS detail fetch failed for %s: %s", source_url, detail_error)
                    return None
                return self.parse_detail_html(detail_html, source_url=source_url, city_slug=city_slug)

        results = await asyncio.gather(*(fetch_detail(item) for item in announcement_urls))
        events = [item for item in results if item is not None]
        if not events:
            self.last_error = "no events parsed from announcement detail pages"
        return events
