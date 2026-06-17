from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.storage.repositories.events import EventRepository
from src.storage.repositories.favorites import FavoritesRepository
from src.storage.schemas import EventDTO


@pytest.mark.asyncio
async def test_favorites_add_and_list(db_runtime) -> None:
    telegram_id = 555001

    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        fav_repo = FavoritesRepository(session)
        event = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/fav/1",
                source_slug="kudago",
                title="Избранное событие",
                category_slug="concerts",
                activity_slug="culture",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=3),
                venue_format="indoor",
            )
        )
        await session.commit()

        await fav_repo.add(telegram_id, event.id)
        await session.commit()

        saved = await fav_repo.list_for_user(telegram_id)

    assert len(saved) == 1
    assert saved[0].id == event.id
    assert saved[0].title == "Избранное событие"


@pytest.mark.asyncio
async def test_favorites_add_is_idempotent(db_runtime) -> None:
    telegram_id = 555002

    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        fav_repo = FavoritesRepository(session)
        event = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/fav/2",
                source_slug="timepad",
                title="Повторное избранное",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=2),
                venue_format="indoor",
            )
        )
        await session.commit()

        await fav_repo.add(telegram_id, event.id)
        await fav_repo.add(telegram_id, event.id)
        await session.commit()

        saved = await fav_repo.list_for_user(telegram_id)

    assert len(saved) == 1
