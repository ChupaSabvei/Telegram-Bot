from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.formatters.events import format_event_list
from src.bot.keyboards.menus import events_keyboard
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
        kb = events_keyboard([event.id for event in events]) if events else None
        await state.update_data(last_list_ids=[event.id for event in events], last_category=category_slug)
        await state.set_state(BotStates.BROWSING_CATEGORY)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
