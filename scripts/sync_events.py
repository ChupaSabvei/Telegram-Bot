from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.scrapers.runner import sync_all_sources
from src.storage.database import build_runtime, init_db, seed_defaults
from src.storage.schemas import CitySlug


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync events from external sources")
    parser.add_argument("--city", choices=[item.value for item in CitySlug], default=None)
    parser.add_argument("--all-cities", action="store_true")
    return parser.parse_args()


async def _run() -> None:
    args = parse_args()
    runtime = build_runtime()
    await init_db(runtime)
    await seed_defaults(runtime)

    if args.city and args.all_cities:
        raise SystemExit("Use either --city or --all-cities")
    if args.city:
        report = await sync_all_sources([args.city])
    else:
        report = await sync_all_sources()

    for item in report.results:
        print(
            f"source={item.source_slug} city={item.city_slug} "
            f"fetched={item.fetched} saved={item.saved} errors={len(item.errors)}"
        )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
