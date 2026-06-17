"""One-time cleanup: remove venue/place URLs and unconfirmed timestamps from the DB."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from src.storage.database import build_runtime
from src.storage.event_filters import is_publishable_event_url, is_plausible_event_timestamp
from src.storage.models import Event
from src.storage.repositories.events import EventRepository


async def main() -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        removed_bad = await repo.delete_unpublishable_events("moscow")
        print(f"Removed unpublishable URLs: {removed_bad}")

        events = list(await session.scalars(select(Event).where(Event.city_slug == "moscow")))
        fake_ts = 0
        for event in events:
            if not event.start_at_confirmed:
                continue
            if is_plausible_event_timestamp(event.start_at, synced_at=event.synced_at):
                continue
            await session.delete(event)
            fake_ts += 1
        if fake_ts:
            await session.flush()
        print(f"Removed fake sync timestamps: {fake_ts}")

        await session.commit()
        print("Cleanup done.")


if __name__ == "__main__":
    asyncio.run(main())
