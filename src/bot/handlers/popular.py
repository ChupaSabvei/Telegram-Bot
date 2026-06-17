from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.formatters.survey_card import format_popular_list
from src.bot.handlers.event_cards import show_viewing_event
from src.bot.keyboards.lists import clean_button_label, list_with_back_keyboard
from src.bot.keyboards.main_menu import main_menu_keyboard
from src.bot.services.ai_discovery import discover_by_query
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.events import EventRepository
from src.storage.repositories.users import UserSettingsRepository

router = Router()


def _popular_keyboard(events: list, *, show_more: bool):
    extra = [("Показать ещё", "popular:more")] if show_more else None
    buttons = [
        (clean_button_label(event.title), f"popular:item:{event.id}")
        for event in events
    ]
    return list_with_back_keyboard(buttons, extra_rows=extra)


@router.callback_query(F.data == "menu:popular")
async def popular_list(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user = await UserSettingsRepository(session).get(callback.from_user.id)
        if user is None:
            await callback.answer("Сначала /start", show_alert=True)
            return
        ranked_events = await EventRepository(session).list_popular(
            user.city_slug,
            limit=10,
            selected_date=user.selected_date,
        )
        all_events = ranked_events
        if not all_events:
            ai_result = await discover_by_query(
                session,
                query="популярные мероприятия на ближайшие дни",
                city_slug=user.city_slug,
                selected_date=user.selected_date,
            )
            if ai_result.events:
                await show_viewing_event(callback, state, ai_result.events[0])
                return
            message = ai_result.clarification or "Пока нет популярных событий в вашем городе."
            try:
                await callback.message.edit_text(message, reply_markup=main_menu_keyboard())
            except TelegramBadRequest:
                await callback.message.answer(message, reply_markup=main_menu_keyboard())
            await callback.answer()
            return
    display = all_events[:5]
    await state.set_state(BotStates.POPULAR_LIST)
    await state.update_data(popular_all=[e.id for e in all_events], popular_shown=5)
    text = format_popular_list(display, selected_date=user.selected_date)
    kb = _popular_keyboard(display, show_more=len(all_events) > 5)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(BotStates.POPULAR_LIST, F.data == "popular:more")
async def popular_more(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    ids = data.get("popular_all", [])
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        events = await EventRepository(session).get_by_ids(ids)
        user = await UserSettingsRepository(session).get(callback.from_user.id)
    display = events[:10]
    text = format_popular_list(display, selected_date=user.selected_date if user else None)
    kb = _popular_keyboard(display, show_more=False)
    await state.update_data(popular_shown=10)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("popular:item:"))
async def popular_open(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = callback.data.split(":")[-1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        event = await EventRepository(session).get_by_id(event_id)
    if event is None:
        await callback.answer("Событие не найдено", show_alert=True)
        return
    await show_viewing_event(callback, state, event)
