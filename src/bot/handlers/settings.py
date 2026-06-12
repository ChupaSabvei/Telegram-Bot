from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.formatters.events import format_main_menu
from src.bot.keyboards.menus import category_keyboard, city_keyboard
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.users import UserSettingsRepository

router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    await state.set_state(BotStates.SETTINGS_CITY)
    await message.answer("Выберите новый город.", reply_markup=city_keyboard())


@router.callback_query(BotStates.SETTINGS_CITY, F.data.startswith("city:"))
async def update_city_from_settings(callback: CallbackQuery, state: FSMContext) -> None:
    city_slug = callback.data.split(":", maxsplit=1)[1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = UserSettingsRepository(session)
        await repo.upsert_city(callback.from_user.id, city_slug)
        await session.commit()
    await state.set_state(BotStates.MAIN_MENU)
    await callback.message.edit_text(format_main_menu(city_slug), reply_markup=category_keyboard())
    await callback.answer("Город обновлен")
