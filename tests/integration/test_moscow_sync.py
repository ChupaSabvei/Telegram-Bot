from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.scrapers.base import ScraperRegistry
from src.scrapers.runner import sync_all_sources
from src.storage.database import build_runtime, init_db, seed_defaults
from src.storage.schemas import EventDTO


class MoscowDummyScraper:
    slug = "timepad"
    name = "Moscow Dummy"
    supported_cities = ("moscow",)

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        if city_slug != "moscow":
            return []
        start_at = datetime.now(tz=UTC) + timedelta(days=4)
        return [
            EventDTO(
                source_url="https://example.com/moscow/timepad/1",
                source_slug="timepad",
                title="Московское событие",
                description="sync test",
                category_slug="other",
                city_slug=city_slug,
                venue="Площадка",
                start_at=start_at,
                price_type="free",
                price_text="Бесплатно",
                venue_format="indoor",
            )
        ]


class SpbDummyScraper:
    slug = "mts_live"
    name = "SPB Dummy"
    supported_cities = ("spb",)

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        if city_slug != "spb":
            return []
        start_at = datetime.now(tz=UTC) + timedelta(days=4)
        return [
            EventDTO(
                source_url="https://example.com/spb/mts/1",
                source_slug="mts_live",
                title="Питерское событие",
                description="should not sync for moscow-only run",
                category_slug="concerts",
                city_slug=city_slug,
                start_at=start_at,
                venue_format="indoor",
            )
        ]


@pytest.mark.asyncio
async def test_moscow_sync_saves_monkeypatched_events(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "moscow_sync.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)

    monkeypatch.setattr("src.scrapers.runner.build_runtime", lambda: runtime)
    monkeypatch.setattr(
        "src.scrapers.runner.build_registry",
        lambda: ScraperRegistry([MoscowDummyScraper(), SpbDummyScraper()]),
    )
    monkeypatch.setattr("src.scrapers.runner._build_classifier", lambda: __import__(
        "src.ai.activity_classifier", fromlist=["ActivityClassifier"]
    ).ActivityClassifier(client=None))

    report = await sync_all_sources(city_slugs=["moscow"])

    assert report.total_saved == 1
    assert report.results[0].city_slug == "moscow"
    assert report.results[0].saved == 1
    assert report.results[1].status == "unsupported"

    async with runtime.session_factory() as session:
        from sqlalchemy import select

        from src.storage.models import Event

        events = list(await session.scalars(select(Event).where(Event.city_slug == "moscow")))
        assert len(events) == 1
        assert events[0].title == "Московское событие"
