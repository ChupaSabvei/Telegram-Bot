from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.handlers import survey
from src.bot.states import BotStates
from src.storage.repositories.events import EventRepository
from src.storage.repositories.users import UserSettingsRepository
from src.storage.schemas import EventDTO


def _callback(data: str, user_id: int = 42) -> MagicMock:
    callback = MagicMock()
    callback.from_user.id = user_id
    callback.data = data
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_survey_fsm_reaches_result_card(db_runtime, monkeypatch) -> None:
    monkeypatch.setattr("src.bot.handlers.survey.build_runtime", lambda: db_runtime)

    async with db_runtime.session_factory() as session:
        await UserSettingsRepository(session).upsert_city(42, "moscow")
        repo = EventRepository(session)
        await repo.upsert_event(
            EventDTO(
                source_url="https://example.com/survey/1",
                source_slug="kudago",
                title="Семейный фестиваль",
                description="Для всей семьи",
                category_slug="other",
                activity_slug="family",
                city_slug="moscow",
                venue="Парк",
                start_at=datetime.now(tz=UTC) + timedelta(days=7),
                price_type="paid",
                price_amount_rub=2000,
                venue_format="outdoor",
                audience_tags=["family"],
                popularity_score=50,
            )
        )
        await session.commit()

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    state = FSMContext(storage=storage, key=key)

    await survey.start_survey(_callback("menu:survey"), state)
    await survey.survey_audience(_callback("survey:aud:family"), state)
    await survey.survey_activity(_callback("survey:act:family"), state)

    budget_callback = _callback("survey:bud:3000")
    await survey.survey_budget(budget_callback, state)

    assert await state.get_state() == BotStates.SURVEY_RESULT.state
    args, _ = budget_callback.message.edit_text.await_args
    assert "Семейный фестиваль" in args[0]
