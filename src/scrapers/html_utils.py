from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup

from src.scrapers.event_dates import MSK, parse_msk_iso
from urllib.parse import urljoin

import httpx

from src.storage.schemas import CATEGORY_SLUGS, CategorySlug, EventDTO, SourceSlug

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_msk_iso(value.strip())
    if parsed is not None:
        return parsed
    raw = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw.replace("Z", "+0000"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=MSK)
            return dt.astimezone(UTC)
        except ValueError:
            continue
    return None


def default_start() -> datetime:
    return datetime.now(tz=UTC) + timedelta(days=7)


def absolutize(base_url: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    return urljoin(base_url, maybe_relative.strip())


def parse_price(price_text: str | None) -> tuple[str, int | None]:
    if not price_text:
        return "unknown", None
    normalized = price_text.lower().strip()
    if "бесплат" in normalized or "free" in normalized:
        return "free", 0
    match = re.search(r"(\d[\d\s]*)", price_text.replace("\u00a0", " "))
    if not match:
        return "unknown", None
    try:
        return "paid", int(match.group(1).replace(" ", ""))
    except ValueError:
        return "paid", None


def map_category_from_text(value: str | None, fallback: CategorySlug = "other") -> CategorySlug:
    if not value:
        return fallback
    text = value.lower()
    mapping: list[tuple[str, CategorySlug]] = [
        ("конц", "concerts"),
        ("music", "concerts"),
        ("театр", "theater"),
        ("theatre", "theater"),
        ("выстав", "exhibitions"),
        ("art", "exhibitions"),
        ("спорт", "sport"),
        ("sport", "sport"),
        ("лекц", "education"),
        ("курс", "education"),
        ("education", "education"),
    ]
    for token, category in mapping:
        if token in text:
            return category
    return fallback


STEALTH_DOMAINS = (
    "afisha.yandex.ru",
    "mtpp.ru",
    "t.me/",
    "vk.ru/",
    "vk.com/",
)


def needs_stealth_proxy(url: str, default: bool) -> bool:
    lowered = url.lower()
    return any(domain in lowered for domain in STEALTH_DOMAINS) or default


async def fetch_html(
    url: str,
    *,
    timeout: float = 15.0,
    headers: dict[str, str] | None = None,
    force_direct: bool = False,
    stealth: bool | None = None,
) -> tuple[str | None, str | None]:
    client_headers = dict(BROWSER_HEADERS)
    if headers:
        client_headers.update(headers)

    if not force_direct:
        from src.config import get_config

        config = get_config()
        bee_timeout = max(timeout, 60.0)
        use_stealth = needs_stealth_proxy(url, config.scrapingbee_stealth if stealth is None else stealth)

        if config.crawlee_enabled:
            from src.scrapers.crawlee_client import fetch_via_crawlee

            html, error = await fetch_via_crawlee(
                url,
                timeout=bee_timeout,
                headers=client_headers,
            )
            if html is not None:
                return html, None
            if error and error not in {"captcha", "crawlee timeout"}:
                return None, error

        if config.scrapingbee_api_key:
            from src.scrapers.scrapingbee import fetch_via_scrapingbee

            html, error = await fetch_via_scrapingbee(
                url,
                api_key=config.scrapingbee_api_key,
                timeout=bee_timeout,
                headers=client_headers,
                stealth=use_stealth,
                premium=config.scrapingbee_premium,
                country_code=config.scrapingbee_country_code,
            )
            if html is not None:
                return html, None
            if error and "limit reached" not in error.lower():
                return None, error

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=client_headers) as client:
            response = await client.get(url)
    except Exception as exc:
        return None, str(exc)
    if response.status_code >= 400:
        return None, f"http {response.status_code}"
    if "captcha" in response.text.lower():
        return None, "captcha"
    return response.text, None


def parse_generic_cards(
    html: str,
    *,
    source_slug: SourceSlug,
    city_slug: str,
    base_url: str,
    card_selector: str = "article, [data-event-card], .event-item",
    fallback_category: CategorySlug = "other",
) -> list[EventDTO]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[EventDTO] = []
    seen_urls: set[str] = set()
    for card in soup.select(card_selector):
        link = card.select_one("h2 a, h3 a, a[href]")
        if link is None:
            continue
        title = link.get_text(strip=True) or (link.get("aria-label") or "").strip()
        source_url = absolutize(base_url, link.get("href"))
        if not title or not source_url or source_url in seen_urls:
            continue

        datetime_raw = (
            card.get("data-start-at")
            or card.get("data-datetime")
            or (card.select_one("time") and card.select_one("time").get("datetime"))
        )
        start_at = parse_datetime(datetime_raw)
        if start_at is None:
            continue
        description_el = card.select_one(".description, .event-description, p")
        description = description_el.get_text(" ", strip=True) if description_el else None
        venue_el = card.select_one(".venue, .place, .event-place")
        venue = venue_el.get_text(" ", strip=True) if venue_el else None
        price_el = card.select_one(".price, [data-price]")
        price_text = None
        if price_el:
            price_text = price_el.get("data-price") or price_el.get_text(" ", strip=True)
        price_type, price_amount = parse_price(price_text)
        category = map_category_from_text(card.get("data-category"), fallback_category)
        image_el = card.select_one("img")
        image_url = absolutize(base_url, image_el.get("src")) if image_el else None

        try:
            events.append(
                EventDTO(
                    source_url=source_url,
                    source_slug=source_slug,
                    title=title,
                    description=description,
                    category_slug=category,
                    city_slug=city_slug,
                    venue=venue,
                    start_at=start_at,
                    start_at_confirmed=True,
                    price_type=price_type,
                    price_text=price_text,
                    price_amount_rub=price_amount,
                    image_url=image_url,
                )
            )
            seen_urls.add(source_url)
        except Exception:
            continue
    return events


def parse_json_ld_events(
    html: str,
    *,
    source_slug: SourceSlug,
    city_slug: str,
    base_url: str,
    fallback_category: CategorySlug = "other",
) -> list[EventDTO]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[EventDTO] = []
    seen_urls: set[str] = set()
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("@type") not in {"Event", "MusicEvent", "Festival"}:
                continue
            source_url = absolutize(base_url, entry.get("url"))
            title = str(entry.get("name") or "").strip()
            if not source_url or not title or source_url in seen_urls:
                continue
            start_at = parse_datetime(entry.get("startDate"))
            if start_at is None:
                continue
            location = entry.get("location")
            venue = None
            address = None
            if isinstance(location, dict):
                venue = location.get("name")
                if isinstance(location.get("address"), dict):
                    address = location["address"].get("streetAddress")
            category = map_category_from_text(str(entry.get("eventAttendanceMode") or ""), fallback_category)
            offers = entry.get("offers")
            price_text = None
            price_amount = None
            price_type = "unknown"
            if isinstance(offers, dict):
                offer_price = offers.get("price")
                if offer_price is not None:
                    price_text = f"{offer_price} ₽"
                    price_type, price_amount = parse_price(price_text)
            image = entry.get("image")
            if isinstance(image, list):
                image = image[0] if image else None
            image_url = absolutize(base_url, image) if isinstance(image, str) else None
            try:
                events.append(
                    EventDTO(
                        source_url=source_url,
                        source_slug=source_slug,
                        title=title,
                        description=(entry.get("description") or "").strip() or None,
                        category_slug=category if category in CATEGORY_SLUGS else fallback_category,
                        city_slug=city_slug,
                        venue=venue,
                        address=address,
                        start_at=start_at,
                        start_at_confirmed=True,
                        price_type=price_type,
                        price_text=price_text,
                        price_amount_rub=price_amount,
                        image_url=image_url,
                    )
                )
                seen_urls.add(source_url)
            except Exception:
                continue
    return events
