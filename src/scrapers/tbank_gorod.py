from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scrapers.event_dates import combine_date_and_time, parse_event_date_from_text
from src.scrapers.html_utils import (
    absolutize,
    fetch_html,
    map_category_from_text,
    parse_json_ld_events,
    parse_price,
)
from src.storage.schemas import CATEGORY_SLUGS, EventDTO

logger = logging.getLogger(__name__)

TBANK_CITY_PATH = {
    "moscow": "moscow",
    "spb": "saint-petersburg",
}

TBANK_CATEGORY_MAP = {
    "concerts": "concerts",
    "cinema": "other",
    "theatres": "theater",
    "theater": "theater",
    "exhibitions": "exhibitions",
    "sport": "sport",
    "education": "education",
}

SKIP_CATEGORIES = frozenset({"places", "collections"})

MAX_DETAIL_FETCHES = 200
DETAIL_CONCURRENCY = 6

EVENT_PATH = re.compile(r"^/gorod/afisha/(?P<city>[^/]+)/(?P<category>[^/]+)/(?P<slug>[^/]+)/?$")
SHOWTIME_PATTERN = re.compile(r"\b(\d{1,2}:\d{2})\b")


class TbankGorodScraper:
    slug = "tbank_gorod"
    name = "T-Bank Город"
    base_url = "https://www.tbank.ru"
    supported_cities = tuple(TBANK_CITY_PATH.keys())
    last_error: str | None = None

    def city_url(self, city_slug: str) -> str | None:
        city_path = TBANK_CITY_PATH.get(city_slug)
        if not city_path:
            return None
        return f"{self.base_url}/gorod/afisha/{city_path}/"

    @classmethod
    def _normalize_event_url(cls, href: str, *, city_path: str) -> str | None:
        href = (href or "").strip()
        if not href:
            return None
        parsed = urlparse(href.split("#", 1)[0])
        path = parsed.path if parsed.scheme else href.split("?", 1)[0].split("#", 1)[0]
        match = EVENT_PATH.match(path)
        if match is None:
            return None
        if match.group("city") != city_path:
            return None
        if match.group("category") in SKIP_CATEGORIES:
            return None
        return f"{cls.base_url}{path.rstrip('/')}/"

    @classmethod
    def collect_event_urls(cls, html: str, *, city_slug: str) -> list[str]:
        city_path = TBANK_CITY_PATH.get(city_slug)
        if not city_path:
            return []
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        urls: list[str] = []
        for link in soup.select('a[href*="/gorod/afisha/"]'):
            source_url = cls._normalize_event_url(link.get("href", ""), city_path=city_path)
            if not source_url or source_url in seen:
                continue
            seen.add(source_url)
            urls.append(source_url)
        return urls

    @classmethod
    def _map_category(cls, source_url: str, fallback: str = "other") -> str:
        path = urlparse(source_url).path.strip("/").split("/")
        if len(path) >= 4:
            mapped = TBANK_CATEGORY_MAP.get(path[3], fallback)
            if mapped in CATEGORY_SLUGS:
                return mapped
        return fallback if fallback in CATEGORY_SLUGS else "other"

    @classmethod
    def _parse_concert_or_theatre(cls, soup: BeautifulSoup, *, source_url: str, city_slug: str) -> EventDTO | None:
        title_el = soup.select_one("h1")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            return None

        date_el = soup.select_one('[data-qa-type="atom-desktop-slot-date"]')
        time_el = soup.select_one('[data-qa-type="atom-desktop-slot-time"]')
        date_text = date_el.get_text(" ", strip=True) if date_el else ""
        time_text = time_el.get_text(" ", strip=True) if time_el else ""
        start_at = combine_date_and_time(date_text, time_text)
        if start_at is None:
            return None

        address_el = soup.select_one('[data-qa-type="desktop-afisha-event-object-object-address"]')
        address = address_el.get_text(" ", strip=True) if address_el else None
        venue = None
        if address and "," in address:
            venue = address.split(",", 1)[0].strip().removeprefix("г. ").strip() or None

        price_el = soup.select_one('[data-qa-type*="price"], [data-qa-type*="event-card-price"]')
        price_text = price_el.get_text(" ", strip=True) if price_el else None
        price_type, price_amount = parse_price(price_text)
        category = cls._map_category(source_url, "concerts")

        try:
            return EventDTO(
                source_url=source_url,
                source_slug="tbank_gorod",
                title=title,
                category_slug=category,  # type: ignore[arg-type]
                city_slug=city_slug,
                venue=venue,
                address=address,
                start_at=start_at,
                start_at_confirmed=True,
                price_type=price_type,
                price_text=price_text,
                price_amount_rub=price_amount,
            )
        except Exception:
            return None

    @classmethod
    def _parse_cinema(cls, soup: BeautifulSoup, *, source_url: str, city_slug: str) -> EventDTO | None:
        title_el = soup.select_one("h1")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            return None

        date_el = soup.select_one('[data-qa-type="atom-desktop-cinema-filters-date-filter-text"]')
        date_text = date_el.get_text(" ", strip=True) if date_el else ""
        if "," in date_text:
            date_text = date_text.split(",", 1)[0].strip()

        schedule = soup.select_one('[data-qa-type="desktop-afisha-cinema-schedule"]')
        schedule_text = schedule.get_text(" ", strip=True) if schedule else ""
        time_match = SHOWTIME_PATTERN.search(schedule_text)

        start_at = None
        if time_match and date_text:
            start_at = combine_date_and_time(date_text, time_match.group(1))
        if start_at is None:
            premiere_el = soup.select_one('[data-qa-type="desktop-afisha-about-cinema-premiere-date-russia"]')
            premiere_text = premiere_el.get_text(" ", strip=True) if premiere_el else ""
            start_at = parse_event_date_from_text(premiere_text)
        if start_at is None:
            return None

        venue = None
        address = None
        if schedule_text:
            before_time = schedule_text.split(time_match.group(1), 1)[0] if time_match else schedule_text
            chunks = [chunk.strip() for chunk in re.split(r"\s{2,}|\d{1,2}:\d{2}", before_time) if chunk.strip()]
            if chunks:
                venue = chunks[0][:120]
            street_match = re.search(r"([А-ЯA-ZЁ][^,]{3,80},\s*\d[\w/-]*)", before_time)
            if street_match:
                address = street_match.group(1).strip()

        try:
            return EventDTO(
                source_url=source_url,
                source_slug="tbank_gorod",
                title=title,
                category_slug="other",
                city_slug=city_slug,
                venue=venue,
                address=address,
                start_at=start_at,
                start_at_confirmed=True,
            )
        except Exception:
            return None

    @classmethod
    def parse_detail_html(cls, html: str, *, source_url: str, city_slug: str) -> EventDTO | None:
        json_ld = parse_json_ld_events(
            html,
            source_slug="tbank_gorod",
            city_slug=city_slug,
            base_url=cls.base_url,
            fallback_category=cls._map_category(source_url),
        )
        if json_ld:
            return json_ld[0]

        soup = BeautifulSoup(html, "html.parser")
        path = urlparse(source_url).path.strip("/").split("/")
        category_segment = path[3] if len(path) >= 4 else ""
        if category_segment == "cinema":
            return cls._parse_cinema(soup, source_url=source_url, city_slug=city_slug)
        return cls._parse_concert_or_theatre(soup, source_url=source_url, city_slug=city_slug)

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

        event_urls = self.collect_event_urls(html, city_slug=city_slug)[:MAX_DETAIL_FETCHES]
        if not event_urls:
            self.last_error = "no event links found on city page"
            return []

        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def fetch_detail(source_url: str) -> EventDTO | None:
            async with semaphore:
                detail_html, detail_error = await fetch_html(
                    source_url,
                    timeout=120.0,
                    headers={"Referer": self.base_url},
                )
                if detail_html is None:
                    logger.debug("T-Bank detail fetch failed for %s: %s", source_url, detail_error)
                    return None
                return self.parse_detail_html(detail_html, source_url=source_url, city_slug=city_slug)

        results = await asyncio.gather(*(fetch_detail(item) for item in event_urls))
        events = [item for item in results if item is not None]
        if not events:
            self.last_error = "no events parsed from detail pages"
        return events
