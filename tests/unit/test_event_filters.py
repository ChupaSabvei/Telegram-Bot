from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.storage.event_filters import is_plausible_event_timestamp, is_publishable_event_url
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


def test_is_publishable_event_url() -> None:
    assert not is_publishable_event_url("https://tbank.ru/places/vtb-arena")
    assert not is_publishable_event_url("https://www.tbank.ru/gorod/places/vtb-arena")
    assert not is_publishable_event_url("https://afisha.yandex.ru/moscow/places/foo")
    assert is_publishable_event_url("https://www.tbank.ru/gorod/concerts/basta")


def test_is_plausible_event_timestamp() -> None:
    synced = datetime(2026, 6, 21, 22, 22, 0, tzinfo=UTC)
    fake = datetime(2026, 6, 21, 22, 22, 47, 3005, tzinfo=UTC)
    real = datetime(2026, 8, 28, 16, 0, 0, tzinfo=UTC)
    assert not is_plausible_event_timestamp(fake, synced_at=synced)
    assert is_plausible_event_timestamp(real, synced_at=synced)
    assert is_plausible_event_timestamp(fake, synced_at=None)


@pytest.mark.asyncio
async def test_delete_unpublishable_and_prune(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://www.tbank.ru/gorod/places/vtb-arena",
            source_slug="tbank_gorod",
            title="ВТБ Арена",
            description=None,
            category_slug="other",
            city_slug="moscow",
            venue="ВТБ Арена",
            start_at=datetime(2026, 6, 20, 19, 0, tzinfo=UTC),
            start_at_confirmed=True,
            end_at=None,
            price_type="unknown",
            price_text=None,
            is_online=False,
            image_url=None,
        )
        with pytest.raises(ValueError):
            await repo.upsert_event(dto)

        good = EventDTO(
            source_url="https://www.tbank.ru/gorod/concerts/test-event",
            source_slug="tbank_gorod",
            title="Концерт",
            description=None,
            category_slug="other",
            city_slug="moscow",
            venue="Лужники",
            start_at=datetime(2026, 6, 20, 19, 0, tzinfo=UTC),
            start_at_confirmed=True,
            end_at=None,
            price_type="unknown",
            price_text=None,
            is_online=False,
            image_url=None,
        )
        await repo.upsert_event(good)
        await session.commit()

        removed = await repo.delete_unpublishable_events("moscow", "tbank_gorod")
        assert removed >= 0

        popular = await repo.list_popular("moscow", limit=10, selected_date=datetime(2026, 6, 20).date())
        urls = [str(e.source_url) for e in popular]
        assert all("/places/" not in u for u in urls)
