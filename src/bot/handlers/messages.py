from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.handlers import search
from src.bot.states import BotStates

router = Router()

SURVEY_PREFIX = "survey:"


@router.message(F.text & ~F.text.startswith("/"))
async def route_free_text(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current in {
        BotStates.SURVEY_AUDIENCE.state,
        BotStates.SURVEY_ACTIVITY.state,
        BotStates.SURVEY_BUDGET.state,
    }:
        await state.clear()
        await state.set_state(BotStates.AI_SEARCH)
    if current == BotStates.COLLECTION_RENAME.state:
        return
    await search.search_events(message, state)
