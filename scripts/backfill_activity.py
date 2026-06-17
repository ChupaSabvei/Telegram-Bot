#!/usr/bin/env python3
"""One-time backfill activity_slug for legacy events (T054)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai.activity_classifier import ActivityClassifier
from src.scrapers.classifiers.activity import classify_activity_rule, infer_audience_tags, infer_venue_format, parse_price_amount_rub
from src.scrapers.runner import _build_classifier, enrich_event_dto
from src.storage.database import build_runtime, init_db, seed_defaults
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO, SourceSlug


async def main() -> None:
    runtime = build_runtime()
    await init_db(runtime)
    await seed_defaults(runtime)
    classifier = _build_classifier()

    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        events = await repo.list_unclassified(limit=5000)
        updated = 0
        for event in events:
            slug: SourceSlug = event.source.slug  # type: ignore[assignment]
            cat_slug = event.category.slug  # type: ignore[union-attr]
            dto = EventDTO(
                source_url=event.source_url,
                source_slug=slug,
                title=event.title,
                description=event.description,
                category_slug=cat_slug,  # type: ignore[arg-type]
                city_slug=event.city_slug,
                venue=event.venue,
                start_at=event.start_at,
                price_type=event.price_type,  # type: ignore[arg-type]
                price_text=event.price_text,
            )
            enriched = await enrich_event_dto(dto, classifier)
            event.activity_slug = enriched.activity_slug
            event.venue_format = enriched.venue_format
            event.audience_tags = enriched.audience_tags
            event.price_amount_rub = enriched.price_amount_rub
            event.popularity_score = enriched.popularity_score
            if enriched.activity_slug:
                updated += 1
        await session.commit()
    print(f"Backfill complete: {updated}/{len(events)} classified")


if __name__ == "__main__":
    asyncio.run(main())
