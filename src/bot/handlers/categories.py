from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.formatters.events import EVENT_MESSAGE_PARSE_MODE, format_event_list, format_main_menu
from src.bot.keyboards.menus import category_keyboard, events_keyboard
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.events import EventRepository
from src.storage.repositories.users import UserSettingsRepository

router = Router()


@router.callback_query(F.data.startswith("cat:"))
async def browse_category(callback: CallbackQuery, state: FSMContext) -> None:
    category_slug = callback.data.split(":", maxsplit=1)[1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user_repo = UserSettingsRepository(session)
        event_repo = EventRepository(session)
        user = await user_repo.get(callback.from_user.id)
        if user is None:
            await callback.answer("Сначала выполните /start", show_alert=True)
            return
        events = await event_repo.list_by_city_category(user.city_slug, category_slug)
        text = format_event_list(events=events, category_slug=category_slug, city_slug=user.city_slug)
        kb = events_keyboard([event.id for event in events], [event.title for event in events])
        await state.update_data(last_list_ids=[event.id for event in events], last_category=category_slug)
        await state.set_state(BotStates.BROWSING_CATEGORY)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
        await callback.answer()


@router.callback_query(F.data == "back:menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user_repo = UserSettingsRepository(session)
        user = await user_repo.get(callback.from_user.id)
        if user is None:
            await callback.answer("Сначала выполните /start", show_alert=True)
            return
    await state.set_state(BotStates.MAIN_MENU)
    await callback.message.edit_text(
        format_main_menu(user.city_slug),
        reply_markup=category_keyboard(),
    )
    await callback.answer()
