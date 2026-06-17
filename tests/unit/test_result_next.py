from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.handlers import random as random_handlers
from src.bot.services.ai_discovery import survey_filters_to_query
from src.bot.services.survey_matcher import SurveyFilters
from src.bot.states import BotStates
from src.storage.repositories.events import EventRepository
from src.storage.repositories.users import UserSettingsRepository
from src.storage.schemas import EventDTO


def _callback(data: str, user_id: int = 42) -> MagicMock:
    callback = MagicMock()
    callback.from_user.id = user_id
    callback.data = data
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def test_survey_filters_to_query() -> None:
    query = survey_filters_to_query(
        SurveyFilters(
            city_slug="moscow",
            audience="family",
            activity="culture",
            budget="1000",
            exclude_ids=[],
        )
    )
    assert "культур" in query.lower()
    assert "семь" in query.lower()
    assert "1000" in query


@pytest.mark.asyncio
async def test_viewing_next_excludes_current_event(db_runtime, monkeypatch) -> None:
    monkeypatch.setattr("src.bot.handlers.random.build_runtime", lambda: db_runtime)

    async with db_runtime.session_factory() as session:
        await UserSettingsRepository(session).upsert_city(42, "moscow")
        repo = EventRepository(session)
        first = await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/1",
                source_slug="kudago",
                title="Событие A",
                description="A",
                category_slug="other",
                activity_slug="culture",
                city_slug="moscow",
                venue="Зал A",
                start_at=datetime.now(tz=UTC) + timedelta(days=3),
                price_type="free",
                venue_format="indoor",
                popularity_score=10,
            )
        )
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/random/2",
                source_slug="kudago",
                title="Событие B",
                description="B",
                category_slug="other",
                activity_slug="culture",
                city_slug="moscow",
                venue="Зал B",
                start_at=datetime.now(tz=UTC) + timedelta(days=4),
                price_type="free",
                venue_format="indoor",
                popularity_score=20,
            )
        )
        await session.commit()
        first_id = first.id

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(BotStates.VIEWING_EVENT)
    await state.update_data(shown_event_ids=[first_id], current_event_id=first_id)

    callback = _callback("result:next")
    await random_handlers.viewing_next(callback, state)

    assert callback.message.edit_text.await_count == 1
    text = callback.message.edit_text.await_args.args[0]
    assert "Событие B" in text
    data = await state.get_data()
    assert first_id in data["shown_event_ids"]
    assert data["current_event_id"] != first_id
