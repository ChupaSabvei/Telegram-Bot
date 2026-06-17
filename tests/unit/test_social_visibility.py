from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from src.storage.models import Event
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


@pytest.mark.asyncio
async def test_social_sources_hidden_when_other_sites_have_data(db_runtime) -> None:
    start_at = datetime.now(tz=UTC) + timedelta(days=4)
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/kudago/1",
                source_slug="kudago",
                title="KudaGo event",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/timepad/1",
                source_slug="timepad",
                title="Timepad event",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        tg_event = await repo.upsert_event(
            EventDTO(
                source_url="https://t.me/channel/stale",
                source_slug="telegram_channels",
                title="Stale TG event",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        await session.commit()

        assert await repo.social_sources_enabled("moscow") is False
        picked = await repo.pick_random("moscow")
        assert picked is not None
        assert picked.id != tg_event.id

        popular = await repo.list_popular("moscow", limit=10)
        assert all(getattr(e.source, "slug", None) != "telegram_channels" for e in popular)


@pytest.mark.asyncio
async def test_social_sources_visible_when_only_kudago_has_data(db_runtime) -> None:
    start_at = datetime.now(tz=UTC) + timedelta(days=4)
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/kudago/only",
                source_slug="kudago",
                title="Only KudaGo",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        tg_event = await repo.upsert_event(
            EventDTO(
                source_url="https://t.me/channel/fallback",
                source_slug="telegram_channels",
                title="Fallback TG event",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        await session.commit()

        assert await repo.social_sources_enabled("moscow") is True
        candidates = await repo.list_candidates_for_ai("moscow", limit=20)
        source_slugs = {getattr(e.source, "slug", None) for e in candidates}
        assert "telegram_channels" in source_slugs


@pytest.mark.asyncio
async def test_social_sources_enabled_for_selected_date_ignores_other_days(db_runtime) -> None:
    from datetime import date

    start_at = datetime.now(tz=UTC) + timedelta(days=4)
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/kudago/date-only",
                source_slug="kudago",
                title="KudaGo on day",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/timepad/other-day",
                source_slug="timepad",
                title="Timepad other day",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at + timedelta(days=10),
                venue_format="indoor",
            )
        )
        await session.commit()

        from src.scrapers.event_dates import MSK, selected_date_range_utc

        day = start_at.astimezone(MSK).date()
        day_start, day_end = selected_date_range_utc(day)
        assert await repo.social_sources_enabled("moscow") is False
        assert await repo.social_sources_enabled("moscow", start=day_start, end=day_end) is True


@pytest.mark.asyncio
async def test_delete_by_source_slug(db_runtime) -> None:
    start_at = datetime.now(tz=UTC) + timedelta(days=4)
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await repo.upsert_event(
            EventDTO(
                source_url="https://t.me/channel/delete-me",
                source_slug="telegram_channels",
                title="Delete me",
                category_slug="other",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        await session.commit()

        deleted = await repo.delete_by_source_slug("moscow", "telegram_channels")
        await session.commit()

        remaining = await session.scalar(
            select(func.count()).select_from(Event).where(Event.city_slug == "moscow")
        )

    assert deleted == 1
    assert remaining == 0
