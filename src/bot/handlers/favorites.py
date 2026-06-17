from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.formatters.survey_card import format_favorite_item
from src.bot.handlers.event_cards import show_viewing_event
from src.bot.keyboards.lists import clean_button_label, list_with_back_keyboard
from src.bot.keyboards.main_menu import main_menu_keyboard
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.events import EventRepository
from src.storage.repositories.favorites import FavoritesRepository

router = Router()


@router.callback_query(F.data == "menu:favorites")
async def favorites_list(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        events = await FavoritesRepository(session).list_for_user(callback.from_user.id)
    if not events:
        try:
            await callback.message.edit_text(
                "Избранное пусто. Сохраняйте события с карточки результата ❤️",
                reply_markup=main_menu_keyboard(),
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "Избранное пусто. Сохраняйте события с карточки результата ❤️",
                reply_markup=main_menu_keyboard(),
            )
        await callback.answer()
        return

    buttons = [
        (clean_button_label(event.title), f"fav:open:{event.id}")
        for event in events
    ]
    lines = ["❤️ Ваше избранное:\n", *[format_favorite_item(event) for event in events]]
    await state.set_state(BotStates.FAVORITES_LIST)
    kb = list_with_back_keyboard(
        buttons,
        extra_rows=[
            ("📋 Подборки", "menu:collections"),
            ("🗑 Очистить избранное", "fav:clear"),
        ],
    )
    text = "\n\n".join(lines)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("fav:open:"))
async def favorites_open(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = callback.data.split(":")[-1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        event = await EventRepository(session).get_by_id(event_id)
    if event is None:
        await callback.answer("Событие не найдено", show_alert=True)
        return
    await show_viewing_event(callback, state, event)


@router.callback_query(F.data == "fav:clear")
async def favorites_clear(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        deleted = await FavoritesRepository(session).clear_for_user(callback.from_user.id)
        await session.commit()
    await callback.answer(f"Удалено: {deleted}")
    await favorites_list(callback, state)
