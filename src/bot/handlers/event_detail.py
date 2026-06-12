from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.formatters.events import EVENT_MESSAGE_PARSE_MODE, format_event_card, format_event_list
from src.bot.keyboards.menus import event_card_keyboard, events_keyboard
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.events import EventRepository
from src.storage.repositories.users import UserSettingsRepository

router = Router()


@router.callback_query(F.data.startswith("evt:"))
async def show_event_card(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = callback.data.split(":", maxsplit=1)[1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = EventRepository(session)
        events = await repo.get_by_ids([event_id])
        if not events:
            await callback.answer("Событие не найдено", show_alert=True)
            return
        event = events[0]
        await state.set_state(BotStates.VIEWING_EVENT)
        await callback.message.edit_text(
            format_event_card(event),
            reply_markup=event_card_keyboard(event.source_url),
            parse_mode=EVENT_MESSAGE_PARSE_MODE,
        )
        await callback.answer()


@router.callback_query(F.data == "back:list")
async def back_to_list(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    event_ids: list[str] = data.get("last_list_ids", [])
    category_slug: str = data.get("last_category", "other")
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        event_repo = EventRepository(session)
        user_repo = UserSettingsRepository(session)
        user = await user_repo.get(callback.from_user.id)
        if user is None:
            await callback.answer("Сначала выполните /start", show_alert=True)
            return
        events = await event_repo.get_by_ids(event_ids)
        await state.set_state(BotStates.BROWSING_CATEGORY)
        await callback.message.edit_text(
            format_event_list(events, category_slug=category_slug, city_slug=user.city_slug),
            reply_markup=events_keyboard(
                [event.id for event in events],
                [event.title for event in events],
            )
            if events
            else None,
            parse_mode=EVENT_MESSAGE_PARSE_MODE,
        )
        await callback.answer()
