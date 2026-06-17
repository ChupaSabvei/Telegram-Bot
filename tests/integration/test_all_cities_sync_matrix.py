from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.scrapers.base import ScraperRegistry
from src.scrapers.runner import sync_all_sources
from src.storage.database import build_runtime, init_db, seed_defaults
from src.storage.schemas import EventDTO


class UniversalDummyScraper:
    slug = "timepad"
    name = "Universal Dummy"
    supported_cities = ("moscow", "spb")

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        start_at = datetime.now(tz=UTC) + timedelta(days=3)
        return [
            EventDTO(
                source_url=f"https://example.com/{city_slug}/u1",
                source_slug="timepad",
                title=f"Universal {city_slug}",
                category_slug="other",
                city_slug=city_slug,
                start_at=start_at,
                venue_format="indoor",
            )
        ]


class MoscowOnlyDummyScraper:
    slug = "mtpp"
    name = "Moscow Only Dummy"
    supported_cities = ("moscow",)

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        start_at = datetime.now(tz=UTC) + timedelta(days=4)
        return [
            EventDTO(
                source_url=f"https://example.com/{city_slug}/m1",
                source_slug="mtpp",
                title=f"Moscow-only {city_slug}",
                category_slug="education",
                city_slug=city_slug,
                start_at=start_at,
                venue_format="indoor",
            )
        ]


@pytest.mark.asyncio
async def test_sync_marks_unsupported_pairs(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "matrix_sync.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)

    monkeypatch.setattr("src.scrapers.runner.build_runtime", lambda: runtime)
    monkeypatch.setattr(
        "src.scrapers.runner.build_registry",
        lambda: ScraperRegistry([UniversalDummyScraper(), MoscowOnlyDummyScraper()]),
    )
    monkeypatch.setattr(
        "src.scrapers.runner._build_classifier",
        lambda: __import__("src.ai.activity_classifier", fromlist=["ActivityClassifier"]).ActivityClassifier(
            client=None
        ),
    )

    report = await sync_all_sources(city_slugs=["moscow", "spb"])
    statuses = {(item.source_slug, item.city_slug): item.status for item in report.results}

    assert statuses[("timepad", "moscow")] == "ok"
    assert statuses[("timepad", "spb")] == "ok"
    assert statuses[("mtpp", "moscow")] == "ok"
    assert statuses[("mtpp", "spb")] == "unsupported"
