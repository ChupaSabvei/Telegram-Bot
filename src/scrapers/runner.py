from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.ai.activity_classifier import ActivityClassifier
from src.ai.client import OpenAIClient
from src.config import get_config
from src.scrapers.base import ScraperProtocol, ScraperRegistry
from src.scrapers.classifiers.activity import (
    classify_activity_rule,
    infer_audience_tags,
    infer_venue_format,
    parse_price_amount_rub,
)
from src.scrapers.kudago import KudaGoScraper
from src.scrapers.mos_kultura import MosKulturaScraper
from src.scrapers.mos_sport_rayon import MosSportRayonScraper
from src.scrapers.mtpp import MtppScraper
from src.scrapers.mts_live import MtsLiveScraper
from src.scrapers.tbank_gorod import TbankGorodScraper
from src.scrapers.telegram_channels import TelegramChannelsScraper
from src.scrapers.timeout_msk import TimeoutMskScraper
from src.scrapers.timepad import TimepadScraper
from src.scrapers.yandex_afisha import YandexAfishaScraper
from src.storage.database import build_runtime
from src.storage.event_filters import is_publishable_event_url
from src.storage.models import EventSource
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO

ACTIVITY_WEIGHT = {
    "sport": 5,
    "kids": 6,
    "family": 7,
    "culture": 8,
    "gastro": 4,
    "relax": 3,
}

from src.scrapers.social_sources import SOCIAL_SOURCE_SLUGS, should_use_social_sources_from_saved


@dataclass(slots=True)
class SyncResult:
    source_slug: str
    city_slug: str
    fetched: int
    saved: int
    status: str = "ok"
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SyncReport:
    results: list[SyncResult] = field(default_factory=list)

    @property
    def total_saved(self) -> int:
        return sum(item.saved for item in self.results)

    @property
    def by_status(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for item in self.results:
            summary[item.status] = summary.get(item.status, 0) + 1
        return summary


def build_registry() -> ScraperRegistry:
    return ScraperRegistry(
        scrapers=[
            KudaGoScraper(),
            YandexAfishaScraper(),
            TimepadScraper(),
            MtsLiveScraper(),
            MosSportRayonScraper(),
            TbankGorodScraper(),
            TimeoutMskScraper(),
            MosKulturaScraper(),
            MtppScraper(),
            TelegramChannelsScraper(),
        ]
    )


def filter_event_window(event: EventDTO, now: datetime | None = None) -> bool:
    now = now or datetime.now(tz=UTC)
    horizon = now + timedelta(days=30)
    return event.start_at > now and event.start_at <= horizon


def compute_popularity_score(dto: EventDTO, *, dedup_bonus: int = 0) -> int:
    now = datetime.now(tz=UTC)
    days = max(0, min(30, (dto.start_at - now).days))
    activity = dto.activity_slug or "culture"
    weight = ACTIVITY_WEIGHT.get(activity, 3)
    # Softer date bias so distant events still appear in lists and random picks.
    return (30 - days) // 2 + dedup_bonus * 5 + weight


def _build_classifier() -> ActivityClassifier:
    cfg = get_config()
    client = None
    if cfg.openai_api_key:
        client = OpenAIClient(
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            base_url=cfg.openai_api_base,
        )
    return ActivityClassifier(client=client)


async def enrich_event_dto(dto: EventDTO, classifier: ActivityClassifier) -> EventDTO:
    dto.venue_format = infer_venue_format(dto)
    dto.audience_tags = infer_audience_tags(dto)
    dto.price_amount_rub = parse_price_amount_rub(dto)
    if dto.activity_slug is None:
        dto.activity_slug = classify_activity_rule(dto)
    if dto.activity_slug is None:
        dto.activity_slug = await classifier.classify(dto)
    dto.popularity_score = compute_popularity_score(dto)
    return dto


async def sync_all_sources(
    city_slugs: list[str] | None = None,
    *,
    source_slugs: list[str] | None = None,
) -> SyncReport:
    from src.storage.schemas import CitySlug

    city_slugs = city_slugs or [city.value for city in CitySlug]
    runtime = build_runtime()
    registry = build_registry()
    scrapers = registry.list_active()
    if source_slugs:
        allowed = set(source_slugs)
        scrapers = [scraper for scraper in scrapers if scraper.slug in allowed]
        unknown = allowed - {scraper.slug for scraper in scrapers}
        if unknown:
            raise ValueError(f"Unknown source slug(s): {', '.join(sorted(unknown))}")
        if not scrapers:
            raise ValueError("No matching sources to sync")
    report = SyncReport()
    classifier = _build_classifier()
    city_saved_by_source: dict[str, dict[str, int]] = {city_slug: {} for city_slug in city_slugs}

    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        for scraper in scrapers:
            supported_cities = set(getattr(scraper, "supported_cities", tuple(city_slugs)))
            for city_slug in city_slugs:
                result = SyncResult(source_slug=scraper.slug, city_slug=city_slug, fetched=0, saved=0)
                report.results.append(result)
                if city_slug not in supported_cities:
                    result.status = "unsupported"
                    continue
                if scraper.slug in SOCIAL_SOURCE_SLUGS and not should_use_social_sources_from_saved(
                    city_saved_by_source.get(city_slug, {})
                ):
                    result.status = "skipped"
                    result.errors.append("Skipped: social source disabled because non-KudaGo sites returned data")
                    deleted = await repo.delete_by_source_slug(city_slug, scraper.slug)
                    if deleted:
                        result.errors.append(f"Removed {deleted} stale social events")
                    source = await session.scalar(select(EventSource).where(EventSource.slug == scraper.slug))
                    if source is not None:
                        source.last_sync_at = datetime.now(tz=UTC)
                        source.last_sync_status = "skipped"
                        source.last_error = result.errors[0]
                    print(f"[sync] {scraper.slug}/{city_slug}: skipped", flush=True)
                    continue
                print(f"[sync] {scraper.slug}/{city_slug}: fetching...", flush=True)
                removed_bad = await repo.delete_unpublishable_events(city_slug, scraper.slug)
                if removed_bad:
                    result.errors.append(f"Removed {removed_bad} unpublishable URLs")

                events = await _safe_fetch(scraper=scraper, city_slug=city_slug, result=result)
                result.fetched = len(events)
                if not events and getattr(scraper, "last_error", None):
                    result.errors.append(str(scraper.last_error))

                saved_urls: set[str] = set()
                for raw in events:
                    if not is_publishable_event_url(str(raw.source_url)):
                        continue
                    if not raw.start_at_confirmed:
                        continue
                    if not filter_event_window(raw):
                        continue
                    try:
                        dto = await enrich_event_dto(raw.model_copy(deep=True), classifier)
                        await repo.upsert_event(dto)
                        saved_urls.add(str(dto.source_url))
                        result.saved += 1
                    except Exception as exc:
                        result.errors.append(str(exc))

                if saved_urls:
                    pruned = await repo.prune_source_except_urls(city_slug, scraper.slug, saved_urls)
                    if pruned:
                        result.errors.append(f"Pruned {pruned} stale events")

                source = await session.scalar(select(EventSource).where(EventSource.slug == scraper.slug))
                if source is not None:
                    source.last_sync_at = datetime.now(tz=UTC)
                    if result.errors and result.saved == 0:
                        source.last_sync_status = "error"
                        result.status = "error"
                    elif result.errors and result.saved > 0:
                        source.last_sync_status = "partial"
                        result.status = "partial"
                    elif result.fetched == 0 and result.saved == 0:
                        source.last_sync_status = "empty"
                        result.status = "empty"
                    else:
                        source.last_sync_status = "ok"
                        result.status = "ok"
                    source.last_error = "; ".join(result.errors[:3]) if result.errors else None
                city_saved_by_source.setdefault(city_slug, {})[scraper.slug] = result.saved
                print(
                    f"[sync] {scraper.slug}/{city_slug}: {result.status} "
                    f"(fetched={result.fetched}, saved={result.saved})",
                    flush=True,
                )

        unclassified = await repo.list_unclassified(limit=100)
        for event in unclassified:
            dto = EventDTO(
                source_url=event.source_url,
                source_slug=event.source.slug,  # type: ignore[union-attr]
                title=event.title,
                description=event.description,
                category_slug=event.category.slug,  # type: ignore[union-attr]
                activity_slug=event.activity_slug,  # type: ignore[arg-type]
                city_slug=event.city_slug,
                venue=event.venue,
                address=event.address,
                start_at=event.start_at,
                end_at=event.end_at,
                price_type=event.price_type,  # type: ignore[arg-type]
                price_text=event.price_text,
                price_amount_rub=event.price_amount_rub,
                venue_format=event.venue_format,  # type: ignore[arg-type]
                audience_tags=event.audience_tags or [],
                is_online=event.is_online,
            )
            enriched = await enrich_event_dto(dto, classifier)
            if enriched.activity_slug:
                event.activity_slug = enriched.activity_slug
                event.venue_format = enriched.venue_format
                event.audience_tags = enriched.audience_tags
                event.price_amount_rub = enriched.price_amount_rub
                event.popularity_score = enriched.popularity_score

        await session.commit()

    return report


async def _safe_fetch(scraper: ScraperProtocol, city_slug: str, result: SyncResult) -> list[EventDTO]:
    try:
        return await scraper.fetch_events(city_slug=city_slug)
    except Exception as exc:
        result.errors.append(str(exc))
        return []
