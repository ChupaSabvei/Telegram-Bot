from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.config import get_config
from src.scrapers.event_dates import parse_event_date_from_text
from src.scrapers.html_utils import map_category_from_text, parse_price, parse_datetime, fetch_html
from src.storage.schemas import EventDTO


class TelegramChannelsScraper:
    slug = "telegram_channels"
    name = "Telegram каналы Москвы"
    supported_cities = ("moscow",)
    base_url = "https://t.me"
    last_error: str | None = None

    @staticmethod
    def _sources() -> list[str]:
        raw = get_config().telegram_channel_sources
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _build_telegram_url(channel: str) -> str:
        return f"https://t.me/s/{channel}"

    @staticmethod
    def _normalize_source(source: str) -> tuple[str, str, str]:
        # returns: platform, slug, canonical_url
        item = source.strip()
        if item.startswith("@"):
            slug = item.lstrip("@")
            return "telegram", slug, TelegramChannelsScraper._build_telegram_url(slug)
        if item.startswith("http://") or item.startswith("https://"):
            parsed = urlparse(item)
            host = parsed.netloc.lower()
            path = parsed.path.strip("/").split("/")
            slug = path[-1] if path else ""
            if "t.me" in host:
                if slug == "s" and len(path) > 1:
                    slug = path[-1]
                return "telegram", slug, TelegramChannelsScraper._build_telegram_url(slug)
            if "vk.ru" in host or "vk.com" in host:
                return "vk", slug, item
        slug = item.lstrip("@")
        return "telegram", slug, TelegramChannelsScraper._build_telegram_url(slug)

    @staticmethod
    def _is_noise_line(line: str) -> bool:
        lowered = line.lower().strip()
        if not lowered:
            return True
        if lowered.startswith("фото:") or lowered.startswith("photo:"):
            return True
        noise_tokens = (
            "подпиш",
            "реклама",
            "по всем вопросам",
            "мы в max",
            "telega.in",
            "max.ru",
            "канал в реестре",
            "источник:",
            "автор фото",
            "фото:",
        )
        if any(token in lowered for token in noise_tokens):
            return True
        if lowered.startswith("@"):
            return True
        return False

    @staticmethod
    def _strip_inline_noise(text: str) -> str:
        cleaned = text
        patterns = (
            r"📚?\s*Фото:\s*[^.!\n]+",
            r"📸[^.!\n]*",
            r"Подпишитесь[^.!\n]*",
            r"\s+в\s+[Mm][Aa][Xx]\b[^.!\n]*",
            r"По всем вопросам[^.!\n]*",
            r"@[\w\d_]+",
        )
        for pattern in patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        return " ".join(cleaned.split())

    @staticmethod
    def _clean_text(text: str) -> str:
        compact = TelegramChannelsScraper._strip_inline_noise(text)
        lines = [line.strip() for line in compact.splitlines()]
        if not lines:
            lines = [compact.strip()]
        cleaned = [line for line in lines if line and not TelegramChannelsScraper._is_noise_line(line)]
        compact = " ".join(cleaned)
        compact = " ".join(compact.split())
        return compact[:2000]

    @staticmethod
    def _title_from_text(text: str) -> str:
        cleaned = TelegramChannelsScraper._clean_text(text)
        if not cleaned:
            return "Событие из канала"
        quoted = re.search(r"[«\"]([^»\"]{8,120})[»\"]", cleaned)
        if quoted:
            return quoted.group(1).strip()[:220]
        candidates = [part.strip() for part in re.split(r"[.!?…]\s+", cleaned) if part.strip()]
        for candidate in candidates:
            if 12 <= len(candidate) <= 120 and not TelegramChannelsScraper._is_noise_line(candidate):
                return candidate[:220]
        first = cleaned.split(" ", maxsplit=14)
        title = " ".join(first)
        return title[:220]

    @staticmethod
    def _resolve_start_at(
        raw_text: str,
        cleaned_text: str,
        post_published: datetime | None,
    ) -> tuple[datetime, bool]:
        now = datetime.now(tz=UTC)
        from_text = parse_event_date_from_text(raw_text, now=now) or parse_event_date_from_text(
            cleaned_text,
            now=now,
        )
        if from_text is not None:
            return from_text, True
        # No explicit event date in the post: keep technical fallback only.
        # UI will hide this date because start_at_confirmed=False.
        fallback = now + timedelta(days=7)
        if fallback.tzinfo is None:
            fallback = fallback.replace(tzinfo=UTC)
        return fallback.astimezone(UTC), False

    async def _fetch_channel_events(self, channel: str, city_slug: str) -> list[EventDTO]:
        html, error = await fetch_html(self._build_telegram_url(channel))
        if html is None:
            self.last_error = f"{channel}: {error}"
            return []

        soup = BeautifulSoup(html, "html.parser")
        events: list[EventDTO] = []
        seen_urls: set[str] = set()
        for post in soup.select(".tgme_widget_message_wrap")[:80]:
            date_el = post.select_one("a.tgme_widget_message_date")
            if date_el is None:
                continue
            source_url = date_el.get("href")
            if not source_url or source_url in seen_urls:
                continue
            seen_urls.add(source_url)

            time_el = date_el.select_one("time")
            post_published = parse_datetime(time_el.get("datetime") if time_el else None)
            text_el = post.select_one(".tgme_widget_message_text")
            text = text_el.get_text(" ", strip=True) if text_el else ""
            if len(text) < 12:
                continue
            cleaned_text = self._clean_text(text)
            if len(cleaned_text) < 12:
                continue
            start_at, start_at_confirmed = self._resolve_start_at(text, cleaned_text, post_published)

            category = map_category_from_text(cleaned_text, "other")
            price_type, _ = parse_price(cleaned_text)
            try:
                events.append(
                    EventDTO(
                        source_url=source_url,
                        source_slug="telegram_channels",
                        title=self._title_from_text(cleaned_text),
                        description=cleaned_text,
                        category_slug=category,
                        city_slug=city_slug,
                        venue=f"Telegram: @{channel}",
                        start_at=start_at,
                        start_at_confirmed=start_at_confirmed,
                        price_type=price_type,
                        price_text=None,
                    )
                )
            except Exception:
                continue
        return events

    async def _fetch_vk_events(self, slug: str, source_url: str, city_slug: str) -> list[EventDTO]:
        html, error = await fetch_html(source_url)
        if html is None:
            self.last_error = f"{slug}: {error}"
            return []

        soup = BeautifulSoup(html, "html.parser")
        events: list[EventDTO] = []
        seen: set[str] = set()
        cards = soup.select(
            ".wall_item, .post, .feed_row, article, [data-post-id], ._post, .post_item",
        )
        for card in cards[:80]:
            text_el = card.select_one(".wall_post_text, .post_text, .pi_text, ._post_content, .copy_post_text")
            text = text_el.get_text(" ", strip=True) if text_el else card.get_text(" ", strip=True)
            if len(text) < 20:
                continue
            cleaned_text = self._clean_text(text)
            if len(cleaned_text) < 20:
                continue

            link_el = card.select_one("a[href*='/wall'], a[href*='w=wall'], a[href*='/public']")
            link = link_el.get("href") if link_el else None
            if not link:
                continue
            if link.startswith("/"):
                link = f"https://vk.ru{link}"
            if link in seen:
                continue
            seen.add(link)

            category = map_category_from_text(cleaned_text, "other")
            price_type, _ = parse_price(cleaned_text)
            start_at, start_at_confirmed = self._resolve_start_at(text, cleaned_text, None)
            try:
                events.append(
                    EventDTO(
                        source_url=link,
                        source_slug="telegram_channels",
                        title=self._title_from_text(cleaned_text),
                        description=cleaned_text,
                        category_slug=category,
                        city_slug=city_slug,
                        venue=f"VK: {slug}",
                        start_at=start_at,
                        start_at_confirmed=start_at_confirmed,
                        price_type=price_type,
                        price_text=None,
                    )
                )
            except Exception:
                continue
        return events

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        self.last_error = None
        if city_slug != "moscow":
            return []
        collected: list[EventDTO] = []
        for raw_source in self._sources():
            platform, slug, source_url = self._normalize_source(raw_source)
            if not slug:
                continue
            if platform == "vk":
                collected.extend(await self._fetch_vk_events(slug, source_url, city_slug))
            else:
                collected.extend(await self._fetch_channel_events(slug, city_slug))
        if not collected and self.last_error is None:
            self.last_error = "no channel events parsed"
        return collected

