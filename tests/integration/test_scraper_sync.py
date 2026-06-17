from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.scrapers.base import ScraperRegistry
from src.scrapers.runner import sync_all_sources
from src.storage.database import build_runtime, init_db, seed_defaults
from src.storage.schemas import EventDTO


class DummyScraper:
    slug = "kudago"
    name = "Dummy"
    supported_cities = ("moscow",)

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        start_at = datetime.now(tz=UTC) + timedelta(days=2)
        return [
            EventDTO(
                source_url=f"https://example.com/{city_slug}/1",
                source_slug="kudago",
                title=f"Событие {city_slug}",
                description="test",
                category_slug="concerts",
                city_slug=city_slug,
                venue="Площадка",
                start_at=start_at,
                end_at=None,
                price_type="free",
                price_text="Бесплатно",
                is_online=False,
            )
        ]


@pytest.mark.asyncio
async def test_sync_pipeline_saves_events(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "sync.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)

    monkeypatch.setattr("src.scrapers.runner.build_runtime", lambda: runtime)
    monkeypatch.setattr("src.scrapers.runner.build_registry", lambda: ScraperRegistry([DummyScraper()]))

    report = await sync_all_sources(city_slugs=["moscow"])
    assert report.total_saved >= 1
