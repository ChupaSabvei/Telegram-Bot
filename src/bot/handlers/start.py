from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.formatters.onboarding import (
    first_launch_guide,
    help_text,
    welcome_city_prompt,
)
from src.bot.handlers.collections import handle_share_start, show_shared_collection
from src.bot.keyboards.main_menu import main_menu_keyboard, main_menu_text
from src.bot.keyboards.menus import city_keyboard
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.repositories.users import UserSettingsRepository

router = Router()


def _parse_share_token(args: str | None) -> str | None:
    if not args:
        return None
    if args.startswith("share_"):
        return args.removeprefix("share_").strip()
    return None


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    share_token = _parse_share_token(command.args)
    if share_token:
        handled = await handle_share_start(message, state, share_token)
        if handled:
            return

    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = UserSettingsRepository(session)
        user = await repo.get(message.from_user.id)
        if user is None or not user.onboarding_complete:
            await state.set_state(BotStates.ONBOARDING_CITY)
            await message.answer(welcome_city_prompt(), reply_markup=city_keyboard())
            return
        await state.set_state(BotStates.MAIN_MENU)
        await message.answer(
            main_menu_text(user.city_slug, user.selected_date),
            reply_markup=main_menu_keyboard(),
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(help_text(), parse_mode="Markdown")


@router.message(Command("categories"))
async def cmd_categories(message: Message) -> None:
    from src.bot.keyboards.menus import category_keyboard

    await message.answer("Выберите категорию (legacy).", reply_markup=category_keyboard())


@router.callback_query(F.data.startswith("city:"))
async def select_city(callback: CallbackQuery, state: FSMContext) -> None:
    city_slug = callback.data.split(":", maxsplit=1)[1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = UserSettingsRepository(session)
        is_first_launch = await repo.get(callback.from_user.id) is None
        await repo.upsert_city(callback.from_user.id, city_slug)
        await session.commit()

    data = await state.get_data()
    pending_share = data.get("pending_share_token")
    if pending_share:
        await state.update_data(pending_share_token=None)
        await show_shared_collection(callback, state, str(pending_share))
        await callback.answer("Город сохранён")
        return

    await state.set_state(BotStates.MAIN_MENU)
    text = first_launch_guide(city_slug) if is_first_launch else main_menu_text(city_slug, None)
    parse_mode = "Markdown" if is_first_launch else None
    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(),
        parse_mode=parse_mode,
    )
    await callback.answer("Город сохранён")


@router.callback_query(F.data == "settings:open")
async def open_settings_from_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BotStates.SETTINGS_CITY)
    await callback.message.edit_text("Выберите новый город.", reply_markup=city_keyboard())
    await callback.answer()
