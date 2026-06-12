from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.scrapers.base import ScraperProtocol, ScraperRegistry
from src.scrapers.kudago import KudaGoScraper
from src.scrapers.yandex_afisha import YandexAfishaScraper
from src.storage.database import build_runtime
from src.storage.models import EventSource
from src.storage.repositories.events import EventRepository
from src.storage.schemas import CitySlug, EventDTO


@dataclass(slots=True)
class SyncResult:
    source_slug: str
    city_slug: str
    fetched: int
    saved: int
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SyncReport:
    results: list[SyncResult] = field(default_factory=list)

    @property
    def total_saved(self) -> int:
        return sum(item.saved for item in self.results)


def build_registry() -> ScraperRegistry:
    return ScraperRegistry(scrapers=[KudaGoScraper(), YandexAfishaScraper()])


def filter_event_window(event: EventDTO, now: datetime | None = None) -> bool:
    now = now or datetime.now(tz=UTC)
    horizon = now + timedelta(days=30)
    return (not event.is_online) and (event.start_at > now) and (event.start_at <= horizon)


async def sync_all_sources(city_slugs: list[str] | None = None) -> SyncReport:
    city_slugs = city_slugs or [city.value for city in CitySlug]
    runtime = build_runtime()
    registry = build_registry()
    report = SyncReport()

    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        for scraper in registry.list_active():
            for city_slug in city_slugs:
                result = SyncResult(source_slug=scraper.slug, city_slug=city_slug, fetched=0, saved=0)
                report.results.append(result)
                events = await _safe_fetch(scraper=scraper, city_slug=city_slug, result=result)
                result.fetched = len(events)

                for event in events:
                    if not filter_event_window(event):
                        continue
                    try:
                        await repo.upsert_event(event)
                        result.saved += 1
                    except Exception as exc:
                        result.errors.append(str(exc))

                source = await session.scalar(select(EventSource).where(EventSource.slug == scraper.slug))
                if source is not None:
                    source.last_sync_at = datetime.now(tz=UTC)
                    if result.errors and result.saved == 0:
                        source.last_sync_status = "error"
                    elif result.errors and result.saved > 0:
                        source.last_sync_status = "partial"
                    else:
                        source.last_sync_status = "ok"
                    source.last_error = "; ".join(result.errors[:3]) if result.errors else None

        await session.commit()

    return report


async def _safe_fetch(scraper: ScraperProtocol, city_slug: str, result: SyncResult) -> list[EventDTO]:
    try:
        return await scraper.fetch_events(city_slug=city_slug)
    except Exception as exc:
        result.errors.append(str(exc))
        return []
