from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


@pytest.mark.asyncio
async def test_list_popular_dedups_by_dedup_group_id(db_runtime) -> None:
    start_at = datetime.now(tz=UTC) + timedelta(days=6)
    group_id = "group-abc-123"

    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        first = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/pop/1",
                source_slug="kudago",
                title="Популярное A",
                category_slug="concerts",
                city_slug="moscow",
                venue="Зал",
                start_at=start_at,
                venue_format="indoor",
                popularity_score=100,
            )
        )
        second = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/pop/2",
                source_slug="yandex_afisha",
                title="Популярное A дубль",
                category_slug="concerts",
                city_slug="moscow",
                venue="Зал",
                start_at=start_at + timedelta(minutes=10),
                venue_format="indoor",
                popularity_score=90,
            )
        )
        first.dedup_group_id = group_id
        second.dedup_group_id = group_id
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/pop/3",
                source_slug="timepad",
                title="Другое популярное",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at + timedelta(days=1),
                venue_format="indoor",
                popularity_score=80,
            )
        )
        await session.commit()

        popular = await repo.list_popular("moscow", limit=10)

    titles = [event.title for event in popular]
    assert titles.count("Популярное A") == 1
    assert titles.count("Популярное A дубль") == 1
    assert "Другое популярное" in titles
    assert len(popular) == 3


@pytest.mark.asyncio
async def test_list_popular_spreads_across_30_days(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        for days_ahead, score, title in (
            (1, 100, "Скоро"),
            (2, 99, "Тоже скоро"),
            (12, 95, "Через две недели"),
            (25, 90, "В конце месяца"),
        ):
            await repo.upsert_event(
                EventDTO(
                    source_url=f"https://example.com/pop/spread/{days_ahead}",
                    source_slug="kudago",
                    title=title,
                    category_slug="concerts",
                    city_slug="moscow",
                    venue="Зал",
                    start_at=datetime.now(tz=UTC) + timedelta(days=days_ahead),
                    venue_format="indoor",
                    popularity_score=score,
                )
            )
        await session.commit()

        popular = await repo.list_popular("moscow", limit=4)

    titles = [event.title for event in popular]
    assert len(titles) == 4
    assert len(set(titles)) == 4
