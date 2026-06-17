from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from src.scrapers.event_dates import combine_date_and_time, parse_event_date_from_text, parse_msk_iso, pick_next_session
from src.storage.event_times import has_explicit_time
from src.scrapers.html_utils import BROWSER_HEADERS, absolutize, fetch_html
from src.storage.schemas import CATEGORY_SLUGS, EventDTO

logger = logging.getLogger(__name__)

URL_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
MAX_DETAIL_FETCHES = 200
DETAIL_CONCURRENCY = 6

YANDEX_CITY_PATH = {
    "moscow": "moscow",
    "spb": "saint-petersburg",
}

YANDEX_CATEGORY_PATH = {
    "concerts": "concert",
    "exhibitions": "art",
    "theater": "theatre",
    "sport": "sport",
    "education": "education",
    "other": "entertainment",
}

YANDEX_HEADERS = {
    **BROWSER_HEADERS,
    "Referer": "https://yandex.ru/",
}

ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
PREFERRED_EVENT_TIMES = ("18:00", "19:00", "20:00", "21:00", "17:00", "16:00")

PRICE_ONLY = re.compile(r"^[\d\s₽%.,+\-]+$")
VENUE_SUFFIX = re.compile(
    r"\b(?:MTC Live|ВТБ Арена|СК «Олимпийский»|Центральный концертный зал|"
    r"Московский международный дом музыки|Adrenaline Stadium|Stadium Live|"
    r"VK Stadium|Сад «Эрмитаж»|Большой театр|CSKA Arena|ЦСКА Арена|"
    r"ВТБ|Стадион)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class YandexDetailInfo:
    start_at: datetime | None = None
    venue: str | None = None
    address: str | None = None
    sessions: list[datetime] | None = None
    page_text: str | None = None


class YandexAfishaScraper:
    slug = "yandex_afisha"
    name = "Yandex Afisha"
    base_url = "https://afisha.yandex.ru"
    supported_cities = tuple(YANDEX_CITY_PATH.keys())
    last_error: str | None = None

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        self.last_error = None
        city_path = YANDEX_CITY_PATH.get(city_slug)
        if not city_path:
            return []

        events: list[EventDTO] = []
        seen_urls: set[str] = set()

        try:
            for category_slug, rubric_path in YANDEX_CATEGORY_PATH.items():
                url = f"{self.base_url}/{city_path}/{rubric_path}"
                page_events, error = await self._fetch_page(url, city_slug, category_slug)
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
        return await self._finalize_event_dates(events)

    @staticmethod
    def _detect_bulk_timestamp(values: list[datetime]) -> datetime | None:
        suspicious = YandexAfishaScraper._suspicious_timestamps(values)
        if not suspicious:
            return None
        counter = Counter(values)
        for timestamp, _count in counter.most_common():
            if timestamp in suspicious:
                return timestamp
        return None

    @staticmethod
    def _suspicious_timestamps(values: list[datetime]) -> set[datetime]:
        if len(values) < 3:
            return set()
        counter = Counter(values)
        threshold = max(3, int(len(values) * 0.08))
        return {timestamp for timestamp, count in counter.items() if count >= threshold}

    @classmethod
    def _has_confirmed_title_date(cls, event: EventDTO) -> bool:
        return parse_event_date_from_text(event.title) is not None

    @classmethod
    def _date_from_url(cls, source_url: str) -> datetime | None:
        match = URL_DATE.search(source_url)
        if not match:
            return None
        return parse_msk_iso(match.group(1))

    @classmethod
    def _resolve_start_at(
        cls,
        *,
        title: str,
        source_url: str,
        description: str | None,
        card_start: datetime | None,
        bulk_timestamp: datetime | None = None,
    ) -> datetime | None:
        from_title = parse_event_date_from_text(title)
        if from_title is not None:
            return from_title
        if description:
            from_description = parse_event_date_from_text(description)
            if from_description is not None:
                return from_description
        from_url = cls._date_from_url(source_url)
        if from_url is not None:
            with_time = parse_event_date_from_text(f"{title} {source_url}")
            if with_time is not None and with_time != from_url:
                return with_time
            return from_url
        if card_start is not None and card_start != bulk_timestamp:
            return card_start
        return None

    async def _finalize_event_dates(self, events: list[EventDTO]) -> list[EventDTO]:
        suspicious = self._suspicious_timestamps([event.start_at for event in events if event.start_at is not None])
        resolved: list[EventDTO] = []
        needs_detail: list[EventDTO] = []

        for event in events:
            title_dt = parse_event_date_from_text(event.title)
            if title_dt is not None:
                event.start_at = title_dt
                event.start_at_confirmed = True
                if not event.venue:
                    needs_detail.append(event)
                else:
                    resolved.append(event)
                continue
            if event.start_at in suspicious:
                needs_detail.append(event)
                continue
            if event.start_at is not None and has_explicit_time(event.start_at):
                if not event.venue:
                    needs_detail.append(event)
                else:
                    resolved.append(event)
                continue
            needs_detail.append(event)

        await self._enrich_from_detail_pages(needs_detail, suspicious=suspicious)
        for event in needs_detail:
            if event.start_at is None:
                continue
            if event.start_at in suspicious and not self._has_confirmed_title_date(event):
                continue
            event.start_at_confirmed = True
            resolved.append(event)

        post_suspicious = self._suspicious_timestamps([event.start_at for event in resolved if event.start_at is not None])
        return [
            event
            for event in resolved
            if event.start_at is not None
            and (event.start_at not in post_suspicious or self._has_confirmed_title_date(event))
        ]

    async def _enrich_from_detail_pages(
        self,
        events: list[EventDTO],
        *,
        suspicious: set[datetime] | None = None,
    ) -> None:
        if not events:
            return
        suspicious = suspicious or set()
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def enrich_one(event: EventDTO) -> None:
            async with semaphore:
                info = await self._fetch_detail_info(str(event.source_url))
                listing_is_bulk = event.start_at in suspicious if event.start_at is not None else False
                if listing_is_bulk and event.start_at is not None:
                    sessions = info.sessions or []
                    resolved = self._resolve_bulk_listing_time(
                        event.start_at,
                        detail_text=info.page_text or "",
                        sessions=sessions,
                        fallback=info.start_at,
                    )
                    if resolved is not None:
                        event.start_at = resolved
                        event.start_at_confirmed = True
                    if sessions:
                        event.session_starts_at = sessions
                elif info.start_at is not None and (
                    event.start_at is None or not has_explicit_time(event.start_at)
                ):
                    event.start_at = info.start_at
                    event.start_at_confirmed = True
                    if info.sessions:
                        event.session_starts_at = info.sessions
                if info.venue and not event.venue:
                    event.venue = info.venue
                if info.address and not event.address:
                    event.address = info.address

        await asyncio.gather(*(enrich_one(event) for event in events[:MAX_DETAIL_FETCHES]))

    @classmethod
    def _extract_html_sessions(cls, html: str) -> list[datetime]:
        sessions: list[datetime] = []
        seen: set[datetime] = set()
        for raw in ISO_DATETIME.findall(html):
            parsed = parse_msk_iso(raw)
            if parsed is None or parsed in seen:
                continue
            seen.add(parsed)
            sessions.append(parsed)
        return sorted(sessions)

    @classmethod
    def _resolve_bulk_listing_time(
        cls,
        listing_start: datetime,
        *,
        detail_text: str,
        sessions: list[datetime],
        fallback: datetime | None,
    ) -> datetime | None:
        from src.scrapers.event_dates import MSK

        listing_day = listing_start.astimezone(MSK).date()
        same_day = [
            session
            for session in sessions
            if session.astimezone(MSK).date() == listing_day and has_explicit_time(session)
        ]
        if same_day:
            return sorted(same_day)[0]

        found_times = [
            match.group(0)
            for match in re.finditer(r"\b([01]?\d|2[0-3]):[0-5]\d\b", detail_text[:15000])
        ]
        for preferred in PREFERRED_EVENT_TIMES:
            if preferred in found_times:
                combined = combine_date_and_time(listing_day.isoformat(), preferred)
                if combined is not None:
                    return combined
        if found_times:
            combined = combine_date_and_time(listing_day.isoformat(), found_times[0])
            if combined is not None:
                return combined
        if sessions:
            return pick_next_session(sessions)
        return fallback

    async def _fetch_detail_info(self, source_url: str) -> YandexDetailInfo:
        html, error = await fetch_html(source_url, timeout=60.0, headers=YANDEX_HEADERS)
        if error or not html:
            return YandexDetailInfo()

        soup = BeautifulSoup(html, "html.parser")
        start_date: str | None = None
        venue: str | None = None
        address: str | None = None
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                payload = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if item.get("@type") != "Event":
                    continue
                start_date = item.get("startDate") or item.get("startTime")
                location = item.get("location")
                if isinstance(location, dict):
                    venue = (location.get("name") or "").strip() or venue
                    raw_address = location.get("address")
                    if isinstance(raw_address, str):
                        address = raw_address.strip() or address
                    elif isinstance(raw_address, dict):
                        address = (raw_address.get("streetAddress") or raw_address.get("name") or "").strip() or address
                if start_date:
                    break
            if start_date:
                break

        text = soup.get_text(" ", strip=True)
        time_match = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", text[:12000])
        if venue is None:
            venue_match = VENUE_SUFFIX.search(text[:8000])
            if venue_match is not None:
                venue = venue_match.group(0).strip()

        start_at: datetime | None = None
        if start_date:
            if "T" in start_date:
                parsed = parse_msk_iso(start_date)
                if parsed is not None and has_explicit_time(parsed):
                    start_at = parsed
            if start_at is None and time_match is not None:
                combined = combine_date_and_time(start_date, time_match.group(0))
                if combined is not None:
                    start_at = combined
            if start_at is None:
                parsed_day = parse_msk_iso(start_date[:10] if "T" not in start_date else start_date.split("T", 1)[0])
                if parsed_day is not None and time_match is not None:
                    combined = combine_date_and_time(start_date, time_match.group(0))
                    start_at = combined or parsed_day
                elif parsed_day is not None and time_match is None:
                    start_at = None
                else:
                    start_at = parsed_day

        if start_at is None:
            from_text = parse_event_date_from_text(text[:5000])
            if from_text is not None:
                start_at = from_text
            else:
                start_at = self._date_from_url(source_url)

        return YandexDetailInfo(
            start_at=start_at,
            venue=venue,
            address=address,
            sessions=self._extract_html_sessions(html),
            page_text=text,
        )

    async def _fetch_detail_datetime(self, source_url: str) -> datetime | None:
        info = await self._fetch_detail_info(source_url)
        return info.start_at

    async def _fetch_page(
        self,
        url: str,
        city_slug: str,
        category_slug: str,
    ) -> tuple[list[EventDTO], str | None]:
        html, error = await fetch_html(url, timeout=60.0, headers=YANDEX_HEADERS)
        if error:
            if error == "captcha":
                return [], "Yandex Afisha returned captcha page"
            return [], f"{url}: {error}"
        if html is None:
            return [], f"{url}: empty response"
        return self._parse_html(html, city_slug, category_slug), None

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
                card_start = parse_msk_iso(start_at_text)
                start_at = self._resolve_start_at(
                    title=title,
                    source_url=str(source_url),
                    description=(card.get("data-description") or "").strip() or None,
                    card_start=card_start,
                )
                if start_at is None:
                    continue
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
                    start_at_confirmed=True,
                    end_at=None,
                    price_type="unknown" if not price_text else "paid",
                    price_text=price_text,
                    is_online=False,
                    image_url=image_url,
                )
            except Exception:
                continue
            events.append(dto)
        if events:
            return events
        return self._parse_links_fallback(soup, city_slug, category_slug)

    @staticmethod
    def _title_from_slug(slug: str) -> str:
        return slug.replace("-", " ").strip().title()

    @classmethod
    def _normalize_event_url(cls, href: str, city_path: str, rubric_path: str) -> str | None:
        href = (href or "").strip()
        if not href or href.startswith("#"):
            return None
        parsed = urlparse(href.split("#", 1)[0])
        path = parsed.path if parsed.scheme else href.split("?", 1)[0].split("#", 1)[0]
        expected_prefix = f"/{city_path}/{rubric_path}/"
        if not path.startswith(expected_prefix):
            if expected_prefix not in path:
                return None
            path = path[path.index(expected_prefix) :]
        path_parts = [part for part in path.strip("/").split("/") if part]
        if len(path_parts) < 3:
            return None
        if path_parts[0] != city_path or path_parts[1] != rubric_path:
            return None
        if path_parts[2] == "places" or "places" in path_parts:
            return None
        slug = path_parts[2]
        if not slug or slug in {rubric_path, city_path, "selection", "all"}:
            return None
        return f"{cls.base_url}/{city_path}/{rubric_path}/{slug}"

    @classmethod
    def _extract_card_context(cls, link: Tag) -> tuple[str, str | None, datetime | None, str | None]:
        title = (link.get("aria-label") or "").strip()
        if title and PRICE_ONLY.match(title):
            title = ""

        container: Tag | None = link
        context_text = ""
        venue: str | None = None
        start_at: datetime | None = None
        price_text: str | None = None

        for _ in range(8):
            if container is None:
                break
            if not title:
                title = link.get_text(" ", strip=True)
            if not title:
                img = container.select_one("img[alt]")
                if img is not None:
                    title = (img.get("alt") or "").strip()
            time_el = container.select_one("time[datetime]")
            if time_el is not None and start_at is None:
                start_at = parse_msk_iso(time_el.get("datetime"))
            text = container.get_text(" ", strip=True)
            if text and len(text) > len(context_text):
                context_text = text
            if venue is None:
                venue_match = VENUE_SUFFIX.search(text)
                if venue_match is not None:
                    venue = venue_match.group(0).strip()
            if price_text is None:
                price_match = re.search(r"от\s+([\d\s]+₽)", text, re.IGNORECASE)
                if price_match is not None:
                    price_text = price_match.group(0).strip()
            if container.parent is None or not isinstance(container.parent, Tag):
                break
            container = container.parent

        if not title and context_text:
            for chunk in re.split(r"\s{2,}|\|", context_text):
                cleaned = chunk.strip()
                if not cleaned or PRICE_ONLY.match(cleaned) or len(cleaned) < 3:
                    continue
                if re.search(r"\d{1,2}\s+(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)", cleaned, re.IGNORECASE):
                    continue
                title = cleaned
                break

        if title and (re.search(r"<br\s*/?>", title, re.IGNORECASE) or re.search(r"^\s*от\s+\d", title, re.IGNORECASE)):
            title = ""
        if start_at is None and context_text:
            start_at = parse_event_date_from_text(context_text)
        return title, venue, start_at, price_text

    def _parse_links_fallback(self, soup: BeautifulSoup, city_slug: str, category_slug: str) -> list[EventDTO]:
        city_path = YANDEX_CITY_PATH.get(city_slug)
        rubric_path = YANDEX_CATEGORY_PATH.get(category_slug, category_slug)
        if not city_path:
            return []

        best_by_url: dict[str, tuple[Tag, str, str | None, datetime | None, str | None]] = {}
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            source_url = self._normalize_event_url(href, city_path, rubric_path)
            if not source_url:
                continue
            title, venue, start_at, price_text = self._extract_card_context(link)
            if not title:
                slug = urlparse(source_url).path.rstrip("/").split("/")[-1]
                title = self._title_from_slug(slug)
            if not title:
                continue
            score = (1 if start_at is not None else 0) + (1 if venue else 0) + min(len(title), 40) // 10
            existing = best_by_url.get(source_url)
            if existing is None or score > existing[0]:
                best_by_url[source_url] = (score, link, title, venue, start_at, price_text)

        events: list[EventDTO] = []
        mapped_category = category_slug if category_slug in CATEGORY_SLUGS else "other"
        for source_url, (_, _link, title, venue, start_at, price_text) in best_by_url.items():
            if "/places/" in source_url:
                continue
            resolved = self._resolve_start_at(
                title=title,
                source_url=source_url,
                description=None,
                card_start=start_at,
            )
            if resolved is None:
                continue
            start_at = resolved
            try:
                dto = EventDTO(
                    external_id=None,
                    source_url=source_url,
                    source_slug=self.slug,
                    title=title,
                    description=None,
                    category_slug=mapped_category,  # type: ignore[arg-type]
                    city_slug=city_slug,
                    venue=venue,
                    start_at=start_at,
                    start_at_confirmed=True,
                    end_at=None,
                    price_type="unknown" if not price_text else "paid",
                    price_text=price_text,
                    is_online=False,
                    image_url=None,
                )
            except Exception:
                continue
            events.append(dto)
        return events
