from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.keyboards.main_menu import main_menu_keyboard, main_menu_text
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.users import UserSettingsRepository

router = Router()


async def open_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user = await UserSettingsRepository(session).get(callback.from_user.id)
        city = user.city_slug if user else "moscow"
        selected_date = user.selected_date if user else None
    await state.set_state(BotStates.MAIN_MENU)
    try:
        await callback.message.edit_text(main_menu_text(city, selected_date), reply_markup=main_menu_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(main_menu_text(city, selected_date), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "nav:main")
async def nav_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await open_main_menu(callback, state)
