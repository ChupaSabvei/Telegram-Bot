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


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = UserSettingsRepository(session)
        user = await repo.get(message.from_user.id)
        if user is None or not user.onboarding_complete:
            await state.set_state(BotStates.ONBOARDING_CITY)
            await message.answer("Привет! Выберите город для подбора мероприятий.", reply_markup=city_keyboard())
            return
        await state.set_state(BotStates.MAIN_MENU)
        await message.answer(format_main_menu(user.city_slug), reply_markup=category_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — главное меню\n"
        "/categories — список категорий\n"
        "/settings — сменить город\n"
        "/help — эта подсказка"
    )


@router.message(Command("categories"))
async def cmd_categories(message: Message) -> None:
    await message.answer("Выберите категорию.", reply_markup=category_keyboard())


@router.callback_query(F.data.startswith("city:"))
async def select_city(callback: CallbackQuery, state: FSMContext) -> None:
    city_slug = callback.data.split(":", maxsplit=1)[1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = UserSettingsRepository(session)
        await repo.upsert_city(callback.from_user.id, city_slug)
        await session.commit()
    await state.set_state(BotStates.MAIN_MENU)
    await callback.message.edit_text(format_main_menu(city_slug), reply_markup=category_keyboard())
    await callback.answer("Город сохранен")
