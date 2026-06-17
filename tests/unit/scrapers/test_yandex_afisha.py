from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.scrapers.event_dates import parse_msk_iso
from src.scrapers.yandex_afisha import YandexAfishaScraper
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


def test_yandex_fallback_parses_dates_and_skips_places() -> None:
    from pathlib import Path

    html = Path("yandex_rendered.html").read_text(encoding="utf-8", errors="ignore")
    scraper = YandexAfishaScraper()
    events = scraper._parse_html(html, "moscow", "concerts")

    assert events
    assert all("/places/" not in str(event.source_url) for event in events)
    assert all(event.start_at_confirmed for event in events)
    assert any("ektomorf" in str(event.source_url) for event in events)
    assert all("₽" not in event.title for event in events)


def test_yandex_normalize_event_url_handles_absolute_links_and_skips_places() -> None:
    scraper = YandexAfishaScraper()
    event_url = scraper._normalize_event_url(
        "https://afisha.yandex.ru/moscow/concert/ektomorf",
        "moscow",
        "concert",
    )
    assert event_url == "https://afisha.yandex.ru/moscow/concert/ektomorf"
    assert scraper._normalize_event_url(
        "https://afisha.yandex.ru/moscow/sport/places/avtodrom-moscow-raceway",
        "moscow",
        "sport",
    ) is None


def test_yandex_fallback_skips_events_without_dates() -> None:
    html = """
    <html><body>
      <a href="https://afisha.yandex.ru/moscow/concert/no-date-event">No date event</a>
    </body></html>
    """
    scraper = YandexAfishaScraper()
    events = scraper._parse_links_fallback(
        __import__("bs4").BeautifulSoup(html, "html.parser"),
        "moscow",
        "concerts",
    )
    assert events == []


def test_yandex_prefers_title_date_over_card_timestamp() -> None:
    scraper = YandexAfishaScraper()
    start_at = scraper._resolve_start_at(
        title="до 10% Кино 21 июня, 19:00",
        source_url="https://afisha.yandex.ru/moscow/concert/kino-2026-06-21",
        description=None,
        card_start=parse_msk_iso("2026-06-16T19:30:00"),
        bulk_timestamp=parse_msk_iso("2026-06-16T19:30:00"),
    )
    assert start_at is not None
    assert start_at.day == 21
    assert start_at.month == 6
    assert start_at.hour == 16  # 19:00 MSK


@pytest.mark.asyncio
async def test_yandex_finalize_uses_title_and_detail() -> None:
    scraper = YandexAfishaScraper()
    events = [
        EventDTO(
            source_url="https://afisha.yandex.ru/moscow/concert/kino-2026-06-21",
            source_slug="yandex_afisha",
            title="до 10% Кино 21 июня, 19:00",
            category_slug="concerts",
            city_slug="moscow",
            venue="Зал",
            start_at=parse_msk_iso("2026-06-16T19:30:00"),
            start_at_confirmed=True,
        ),
    ]
    finalized = await scraper._finalize_event_dates(events)
    assert len(finalized) == 1
    assert finalized[0].start_at.day == 21
    assert finalized[0].start_at.month == 6


@pytest.mark.asyncio
async def test_interleave_avoids_consecutive_same_source(db_runtime) -> None:
    start_at = datetime.now(tz=UTC) + timedelta(days=6)
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        group_id = "group-popular-mix"
        for idx, (source_slug, score, title) in enumerate(
            (
                ("kudago", 100, "KudaGo top"),
                ("yandex_afisha", 99, "Yandex top"),
                ("timepad", 98, "Timepad top"),
                ("mts_live", 97, "MTS top"),
            )
        ):
            event = await repo.upsert_event(
                EventDTO(
                    source_url=f"https://example.com/pop/mix/{source_slug}",
                    source_slug=source_slug,  # type: ignore[arg-type]
                    title=title,
                    category_slug="concerts",
                    city_slug="moscow",
                    venue="Зал",
                    start_at=start_at + timedelta(hours=idx),
                    venue_format="indoor",
                    popularity_score=score,
                )
            )
            event.dedup_group_id = group_id
        await session.commit()

        popular = await repo.list_popular("moscow", limit=4)

    sources = {event.source.slug for event in popular}
    assert len(popular) == 4
    assert len(sources) >= 3
    slugs = [event.source.slug for event in popular]
    for left, right in zip(slugs, slugs[1:], strict=False):
        if len(sources) > 1:
            assert left != right


@pytest.mark.asyncio
async def test_list_popular_top_results_are_source_diverse(db_runtime) -> None:
    start_at = datetime.now(tz=UTC) + timedelta(days=3)
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        for idx in range(12):
            await repo.upsert_event(
                EventDTO(
                    source_url=f"https://example.com/pop/kudago/{idx}",
                    source_slug="kudago",
                    title=f"KudaGo {idx}",
                    category_slug="concerts",
                    city_slug="moscow",
                    venue="Зал",
                    start_at=start_at + timedelta(hours=idx),
                    venue_format="indoor",
                    popularity_score=200 - idx,
                )
            )
        for source_slug, score, title in (
            ("yandex_afisha", 50, "Yandex pick"),
            ("mts_live", 49, "MTS pick"),
            ("tbank_gorod", 48, "T-Bank pick"),
        ):
            await repo.upsert_event(
                EventDTO(
                    source_url=f"https://example.com/pop/{source_slug}",
                    source_slug=source_slug,  # type: ignore[arg-type]
                    title=title,
                    category_slug="concerts",
                    city_slug="moscow",
                    venue="Зал",
                    start_at=start_at + timedelta(days=1),
                    venue_format="indoor",
                    popularity_score=score,
                )
            )
        await session.commit()

        popular = await repo.list_popular("moscow", limit=5)

    top_sources = {event.source.slug for event in popular}
    assert len(top_sources) >= 3


def test_yandex_bulk_listing_time_uses_detail_evening_time() -> None:
    scraper = YandexAfishaScraper()
    listing = parse_msk_iso("2026-06-27T11:30:00")
    assert listing is not None
    resolved = scraper._resolve_bulk_listing_time(
        listing,
        detail_text="5 сентября, суббота, 18:00 билеты на сайте",
        sessions=[parse_msk_iso("2026-09-05T18:00:00")],
        fallback=None,
    )
    assert resolved is not None
    assert resolved.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m %H:%M") == "27.06 18:00"
