from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.scrapers.event_dates import MSK, combine_date_and_time, parse_event_date_from_text, parse_msk_iso
from src.scrapers.mts_live import MtsLiveScraper
from src.scrapers.tbank_gorod import TbankGorodScraper


def test_parse_msk_iso_treats_naive_as_moscow() -> None:
    parsed = parse_msk_iso("2026-08-28T19:00:00")
    assert parsed is not None
    assert parsed.astimezone(UTC).hour == 16


def test_combine_date_and_time() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    parsed = combine_date_and_time("28 августа", "19:00", now=now)
    assert parsed is not None
    assert parsed.astimezone(UTC).hour == 16


def test_parse_event_date_from_text_supports_from_day_pattern() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    parsed = parse_event_date_from_text("2026, \u0430\u0432\u0433\u0443\u0441\u0442 \u0441 28 \u0430\u0432\u0433\u0443\u0441\u0442\u0430", now=now)
    assert parsed is not None
    assert parsed.astimezone(MSK).month == 8
    assert parsed.astimezone(MSK).day == 28


def test_mts_parse_detail_html(mts_live_detail_html: str) -> None:
    event = MtsLiveScraper.parse_detail_html(
        mts_live_detail_html,
        source_url="https://live.mts.ru/moscow/announcements/basta-guf?eventId=28754837",
        city_slug="moscow",
    )
    assert event is not None
    assert event.title == "Баста и Гуф"
    assert event.start_at_confirmed is True
    assert event.address == "г. Москва, ул. Лужники, 24с1"
    assert event.venue == "Лужники"


def test_tbank_collect_event_urls_skips_places(tbank_gorod_html: str) -> None:
    html = """
    <a href="/gorod/afisha/moscow/places/circus-1/">Цирк</a>
    <a href="/gorod/afisha/moscow/concerts/basta-123/">Баста</a>
    """
    urls = TbankGorodScraper.collect_event_urls(html, city_slug="moscow")
    assert len(urls) == 1
    assert "/concerts/basta-123/" in urls[0]
    assert "/places/" not in urls[0]


def test_tbank_parse_concert_detail_html(tbank_concert_detail_html: str) -> None:
    event = TbankGorodScraper.parse_detail_html(
        tbank_concert_detail_html,
        source_url="https://www.tbank.ru/gorod/afisha/moscow/concerts/basta-guf-539245/",
        city_slug="moscow",
    )
    assert event is not None
    assert event.title == "Баста-Гуф"
    assert event.start_at_confirmed is True
    assert event.address == "г. Москва, ул. Лужники, 24с1"
    assert event.start_at.astimezone(UTC).hour == 16
