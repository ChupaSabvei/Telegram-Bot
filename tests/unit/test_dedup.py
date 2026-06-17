from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.storage.database import build_runtime, init_db, seed_defaults
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


@pytest.mark.asyncio
async def test_dedup_assigns_group_for_similar_events(tmp_path) -> None:
    db_path = tmp_path / "dedup.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)

    start_at = datetime.now(tz=UTC) + timedelta(days=5)

    dto_1 = EventDTO(
        source_url="https://example.com/source-a/1",
        source_slug="kudago",
        title="Джазовый концерт в клубе",
        description="Описание 1",
        category_slug="concerts",
        city_slug="moscow",
        venue="Клуб 16 тонн",
        start_at=start_at,
        end_at=None,
        price_type="paid",
        price_text="от 2000 ₽",
        is_online=False,
    )
    dto_2 = EventDTO(
        source_url="https://example.com/source-b/777",
        source_slug="yandex_afisha",
        title="Джазовый концерт в клубе 16 тонн",
        description="Описание 2",
        category_slug="concerts",
        city_slug="moscow",
        venue="16 тонн",
        start_at=start_at + timedelta(minutes=5),
        end_at=None,
        price_type="paid",
        price_text="от 1800 ₽",
        is_online=False,
    )

    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        first = await repo.upsert_event(dto_1)
        second = await repo.upsert_event(dto_2)
        await session.commit()

        assert first.dedup_group_id is not None
        assert second.dedup_group_id == first.dedup_group_id


@pytest.mark.asyncio
async def test_dedup_skips_empty_venue_title_only_match(tmp_path) -> None:
    db_path = tmp_path / "dedup-empty-venue.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)

    start_at = datetime.now(tz=UTC) + timedelta(days=5)
    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        first = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/yandex/1",
                source_slug="yandex_afisha",
                title="Rec Gran Pri Sportsa",
                category_slug="sport",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        second = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/tbank/1",
                source_slug="tbank_gorod",
                title="Rec Gran Pri Sport Fest",
                category_slug="sport",
                city_slug="moscow",
                start_at=start_at,
                venue_format="indoor",
            )
        )
        await session.commit()

    assert first.dedup_group_id is None
    assert second.dedup_group_id is None
