from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from src.scrapers.base import ScraperRegistry
from src.scrapers.runner import sync_all_sources
from src.storage.database import build_runtime, init_db, seed_defaults
from src.storage.models import Event
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


class DummyKudaGoScraper:
    slug = "kudago"
    name = "Dummy KudaGo"
    supported_cities = ("moscow",)

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        start_at = datetime.now(tz=UTC) + timedelta(days=4)
        return [
            EventDTO(
                source_url="https://example.com/kudago/1",
                source_slug="kudago",
                title="KudaGo only",
                category_slug="other",
                city_slug=city_slug,
                start_at=start_at,
                venue_format="indoor",
            )
        ]


class DummyTimepadScraper:
    slug = "timepad"
    name = "Dummy Timepad"
    supported_cities = ("moscow",)

    def __init__(self, *, with_events: bool) -> None:
        self.with_events = with_events

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        if not self.with_events:
            return []
        start_at = datetime.now(tz=UTC) + timedelta(days=4)
        return [
            EventDTO(
                source_url="https://example.com/timepad/1",
                source_slug="timepad",
                title="Timepad event",
                category_slug="other",
                city_slug=city_slug,
                start_at=start_at,
                venue_format="indoor",
            )
        ]


class DummyTelegramScraper:
    slug = "telegram_channels"
    name = "Dummy Telegram"
    supported_cities = ("moscow",)
    calls = 0

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        DummyTelegramScraper.calls += 1
        start_at = datetime.now(tz=UTC) + timedelta(days=4)
        return [
            EventDTO(
                source_url=f"https://t.me/channel/{DummyTelegramScraper.calls}",
                source_slug="telegram_channels",
                title="Telegram event",
                category_slug="other",
                city_slug=city_slug,
                start_at=start_at,
                venue_format="indoor",
            )
        ]


@pytest.mark.asyncio
async def test_social_source_skipped_when_non_kudago_site_has_data(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "social_skip.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)
    DummyTelegramScraper.calls = 0

    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        stale = await repo.upsert_event(
            EventDTO(
                source_url="https://t.me/channel/stale",
                source_slug="telegram_channels",
                title="Stale telegram event",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=4),
                venue_format="indoor",
            )
        )
        await session.commit()
        stale_id = stale.id

    monkeypatch.setattr("src.scrapers.runner.build_runtime", lambda: runtime)
    monkeypatch.setattr(
        "src.scrapers.runner.build_registry",
        lambda: ScraperRegistry(
            [DummyKudaGoScraper(), DummyTimepadScraper(with_events=True), DummyTelegramScraper()]
        ),
    )
    monkeypatch.setattr(
        "src.scrapers.runner._build_classifier",
        lambda: __import__("src.ai.activity_classifier", fromlist=["ActivityClassifier"]).ActivityClassifier(
            client=None
        ),
    )

    report = await sync_all_sources(city_slugs=["moscow"])
    statuses = {(item.source_slug, item.city_slug): item.status for item in report.results}

    assert statuses[("kudago", "moscow")] == "ok"
    assert statuses[("timepad", "moscow")] == "ok"
    assert statuses[("telegram_channels", "moscow")] == "skipped"
    assert DummyTelegramScraper.calls == 0

    async with runtime.session_factory() as session:
        remaining = await session.scalar(
            select(func.count()).select_from(Event).where(Event.id == stale_id)
        )
    assert remaining == 0


@pytest.mark.asyncio
async def test_social_source_runs_when_only_kudago_has_data(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "social_run.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)
    DummyTelegramScraper.calls = 0

    monkeypatch.setattr("src.scrapers.runner.build_runtime", lambda: runtime)
    monkeypatch.setattr(
        "src.scrapers.runner.build_registry",
        lambda: ScraperRegistry(
            [DummyKudaGoScraper(), DummyTimepadScraper(with_events=False), DummyTelegramScraper()]
        ),
    )
    monkeypatch.setattr(
        "src.scrapers.runner._build_classifier",
        lambda: __import__("src.ai.activity_classifier", fromlist=["ActivityClassifier"]).ActivityClassifier(
            client=None
        ),
    )

    report = await sync_all_sources(city_slugs=["moscow"])
    statuses = {(item.source_slug, item.city_slug): item.status for item in report.results}

    assert statuses[("kudago", "moscow")] == "ok"
    assert statuses[("timepad", "moscow")] == "empty"
    assert statuses[("telegram_channels", "moscow")] == "ok"
    assert DummyTelegramScraper.calls == 1
