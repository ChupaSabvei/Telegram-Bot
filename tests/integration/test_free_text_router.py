from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.handlers.messages import route_free_text
from src.bot.states import BotStates


@pytest.mark.asyncio
async def test_free_text_clears_survey_state(monkeypatch) -> None:
    search_mock = AsyncMock()
    monkeypatch.setattr("src.bot.handlers.messages.search.search_events", search_mock)

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(BotStates.SURVEY_BUDGET)
    await state.update_data(audience="family", activity="culture", budget="1000")

    message = MagicMock()
    message.text = "бильярд рядом"
    message.from_user.id = 1

    await route_free_text(message, state)

    assert await state.get_state() == BotStates.AI_SEARCH.state
    data = await state.get_data()
    assert "audience" not in data
    search_mock.assert_awaited_once_with(message, state)
