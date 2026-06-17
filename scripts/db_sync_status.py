from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from src.storage.database import build_runtime, init_db
from src.storage.models import Event, EventSource


async def main() -> None:
    runtime = build_runtime()
    await init_db(runtime)
    async with runtime.session_factory() as session:
        sources = (await session.execute(select(EventSource).order_by(EventSource.slug))).scalars().all()
        print("=== Last sync status ===")
        for source in sources:
            err = (source.last_error or "")[:120]
            print(f"{source.slug:20} {source.last_sync_status or '-':8}  {err}")

        print("\n=== Events in DB (moscow) ===")
        rows = (
            await session.execute(
                select(EventSource.slug, func.count(Event.id))
                .join(Event, Event.source_id == EventSource.id)
                .where(Event.city_slug == "moscow")
                .group_by(EventSource.slug)
                .order_by(EventSource.slug)
            )
        ).all()
        for slug, count in rows:
            print(f"{slug:20} {count}")


if __name__ == "__main__":
    asyncio.run(main())
