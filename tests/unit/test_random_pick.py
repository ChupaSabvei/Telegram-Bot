from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


@pytest.mark.asyncio
async def test_pick_random_returns_event_in_city(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://example.com/random/1",
            source_slug="kudago",
            title="Случайное событие",
            category_slug="other",
            activity_slug="culture",
            city_slug="moscow",
            start_at=datetime.now(tz=UTC) + timedelta(days=4),
            venue_format="indoor",
        )
        saved = await repo.upsert_event(dto)
        await session.commit()

        picked = await repo.pick_random("moscow")
        assert picked is not None
        assert picked.id == saved.id


@pytest.mark.asyncio
async def test_pick_random_respects_exclude_ids(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        first = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/a",
                source_slug="kudago",
                title="A",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=4),
                venue_format="indoor",
            )
        )
        second = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/b",
                source_slug="kudago",
                title="B",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=5),
                venue_format="indoor",
            )
        )
        await session.commit()

        picked = await repo.pick_random("moscow", exclude_ids=[first.id])
        assert picked is not None
        assert picked.id == second.id


@pytest.mark.asyncio
async def test_pick_random_excludes_telegram_when_other_sources_have_data(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        kudago_event = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/kudago",
                source_slug="kudago",
                title="KudaGo event",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=3),
                venue_format="indoor",
            )
        )
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/timepad",
                source_slug="timepad",
                title="Timepad event",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=3),
                venue_format="indoor",
            )
        )
        tg_event = await repo.upsert_event(
            EventDTO(
                source_url="https://t.me/channel/1",
                source_slug="telegram_channels",
                title="TG event",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime.now(tz=UTC) + timedelta(days=3),
                venue_format="indoor",
            )
        )
        await session.commit()

        picked = await repo.pick_random("moscow")

    assert picked is not None
    assert picked.id != tg_event.id
    assert getattr(getattr(picked, "source", None), "slug", None) != "telegram_channels"


@pytest.mark.asyncio
async def test_pick_random_selected_date_uses_moscow_day_boundaries(db_runtime) -> None:
    # 2026-06-20 22:30 UTC = 2026-06-21 01:30 MSK, should match selected_date=2026-06-21
    start_at = datetime(2026, 6, 20, 22, 30, tzinfo=UTC)
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        event = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/date-msk",
                source_slug="kudago",
                title="MSK date boundary event",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        await session.commit()

        picked = await repo.pick_random("moscow", selected_date=date(2026, 6, 21))

    assert picked is not None
    assert picked.id == event.id


@pytest.mark.asyncio
async def test_pick_random_includes_telegram_when_only_kudago_has_data(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/kudago-only-date",
                source_slug="kudago",
                title="Only KudaGo on date",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime(2026, 6, 21, 10, 0, tzinfo=UTC),
                venue_format="indoor",
            )
        )
        tg_event = await repo.upsert_event(
            EventDTO(
                source_url="https://t.me/channel/fallback",
                source_slug="telegram_channels",
                title="TG fallback",
                category_slug="other",
                city_slug="moscow",
                start_at=datetime(2026, 6, 21, 11, 0, tzinfo=UTC),
                venue_format="indoor",
            )
        )
        await session.commit()

        candidates = await repo.list_candidates_for_ai("moscow", selected_date=date(2026, 6, 21))
        source_slugs = {item.source.slug for item in candidates}

    assert "telegram_channels" in source_slugs
    assert tg_event.id in {item.id for item in candidates}
