from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.handlers.event_cards import show_viewing_event
from src.bot.handlers.navigation import open_main_menu
from src.bot.keyboards.main_menu import main_menu_keyboard
from src.bot.services.ai_discovery import discover_by_query
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.events import EventRepository
from src.storage.repositories.users import UserSettingsRepository

router = Router()


async def _pick_random_variant(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user = await UserSettingsRepository(session).get(callback.from_user.id)
        if user is None:
            await callback.answer("Сначала /start", show_alert=True)
            return

        data = await state.get_data()
        shown = list(data.get("shown_event_ids", []))
        current = data.get("current_event_id")
        if current and current not in shown:
            shown.append(current)

        repo = EventRepository(session)
        event = await repo.pick_random(
            user.city_slug,
            exclude_ids=shown,
            selected_date=user.selected_date,
        )
        if event is None and user.selected_date is not None and shown:
            event = await repo.pick_random(
                user.city_slug,
                exclude_ids=None,
                selected_date=user.selected_date,
            )
        if event is not None:
            await show_viewing_event(callback, state, event)
            return

        ai_result = await discover_by_query(
            session,
            query="интересное мероприятие на ближайшие дни",
            city_slug=user.city_slug,
            exclude_ids=shown,
            selected_date=user.selected_date,
        )

    if ai_result.events:
        await show_viewing_event(callback, state, ai_result.events[0])
        return

    text = ai_result.clarification or (
        "Пока нет событий в вашем городе. Попробуйте позже или опишите запрос текстом."
    )
    try:
        await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:random")
async def random_variant(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BotStates.VIEWING_EVENT)
    await state.update_data(shown_event_ids=[])
    await _pick_random_variant(callback, state)


@router.callback_query(BotStates.VIEWING_EVENT, F.data == "result:next")
async def viewing_next(callback: CallbackQuery, state: FSMContext) -> None:
    await _pick_random_variant(callback, state)


@router.callback_query(BotStates.VIEWING_EVENT, F.data == "result:restart")
async def random_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await open_main_menu(callback, state)
