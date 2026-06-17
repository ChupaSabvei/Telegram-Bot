#!/usr/bin/env python3
"""Count events for Moscow gate and all-city coverage health."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from src.storage.database import build_runtime, init_db
from src.storage.models import Event, EventSource


async def count_city(
    city_slug: str,
    *,
    min_events: int,
    min_sources: int,
) -> tuple[bool, bool]:
    runtime = build_runtime()
    await init_db(runtime)
    now = datetime.now(tz=UTC)
    horizon = now + timedelta(days=30)

    async with runtime.session_factory() as session:
        total = await session.scalar(
            select(func.count(Event.id)).where(
                Event.city_slug == city_slug,
                Event.start_at > now,
                Event.start_at <= horizon,
            )
        )
        rows = await session.execute(
            select(EventSource.slug, func.count(Event.id))
            .join(Event, Event.source_id == EventSource.id)
            .where(
                Event.city_slug == city_slug,
                Event.start_at > now,
                Event.start_at <= horizon,
            )
            .group_by(EventSource.slug)
        )
        by_source = Counter({slug: count for slug, count in rows.all() if count > 0})

    print(f"{city_slug} events (30d): {total}")
    for slug, count in sorted(by_source.items()):
        print(f"  {slug}: {count}")
    sources_ok = len(by_source)
    events_ok = (total or 0) >= min_events
    sources_pass = sources_ok >= min_sources
    print(
        f"gate[{city_slug}]: events>={min_events} {'PASS' if events_ok else 'FAIL'}, "
        f"sources>={min_sources} {'PASS' if sources_pass else 'FAIL'}"
    )
    return events_ok, sources_pass


async def count_all_cities(min_events: int = 30, min_sources: int = 2) -> int:
    from src.storage.schemas import CitySlug

    failed: list[str] = []
    for city in CitySlug:
        events_ok, sources_ok = await count_city(
            city.value,
            min_events=min_events,
            min_sources=min_sources,
        )
        if not (events_ok and sources_ok):
            failed.append(city.value)
    if failed:
        print(f"all-cities coverage FAIL: {', '.join(failed)}")
        return 1
    print("all-cities coverage PASS")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Event count gates")
    parser.add_argument("--city", default="moscow")
    parser.add_argument("--min-events", type=int, default=200)
    parser.add_argument("--min-sources", type=int, default=5)
    parser.add_argument("--all-cities", action="store_true")
    args = parser.parse_args()
    if args.all_cities:
        raise SystemExit(asyncio.run(count_all_cities(args.min_events, args.min_sources)))
    events_ok, sources_ok = asyncio.run(
        count_city(args.city, min_events=args.min_events, min_sources=args.min_sources)
    )
    raise SystemExit(0 if events_ok and sources_ok else 1)


if __name__ == "__main__":
    main()
