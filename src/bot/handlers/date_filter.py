from __future__ import annotations

from datetime import UTC, date, datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.keyboards.calendar import month_keyboard
from src.bot.keyboards.main_menu import main_menu_keyboard, main_menu_text
from src.storage.database import build_runtime
from src.storage.repositories.users import UserSettingsRepository

router = Router()


def _month_from_callback(value: str | None) -> date:
    if not value:
        today = datetime.now(tz=UTC).date()
        return date(today.year, today.month, 1)
    try:
        parsed = date.fromisoformat(value)
        return date(parsed.year, parsed.month, 1)
    except ValueError:
        today = datetime.now(tz=UTC).date()
        return date(today.year, today.month, 1)


@router.callback_query(F.data == "menu:date")
async def open_date_picker(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user = await UserSettingsRepository(session).get(callback.from_user.id)
    selected = user.selected_date if user else None
    month = date(selected.year, selected.month, 1) if selected else datetime.now(tz=UTC).date().replace(day=1)
    await state.update_data(calendar_month=month.isoformat())
    await callback.message.edit_text(
        "Выберите дату для поиска событий:",
        reply_markup=month_keyboard(month, selected),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("date:month:"))
async def date_change_month(callback: CallbackQuery, state: FSMContext) -> None:
    month = _month_from_callback(callback.data.split(":", maxsplit=2)[-1])
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user = await UserSettingsRepository(session).get(callback.from_user.id)
    selected = user.selected_date if user else None
    await state.update_data(calendar_month=month.isoformat())
    await callback.message.edit_reply_markup(reply_markup=month_keyboard(month, selected))
    await callback.answer()


@router.callback_query(F.data.startswith("date:pick:"))
async def date_pick(callback: CallbackQuery, state: FSMContext) -> None:
    payload = callback.data.split(":", maxsplit=2)[-1]
    chosen = date.fromisoformat(payload)
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = UserSettingsRepository(session)
        user = await repo.set_selected_date(callback.from_user.id, chosen)
        await session.commit()
    city = user.city_slug if user else "moscow"
    await callback.message.edit_text(
        main_menu_text(city, chosen),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer(f"Дата установлена: {chosen.strftime('%d.%m.%Y')}")


@router.callback_query(F.data == "date:clear")
async def date_clear(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        repo = UserSettingsRepository(session)
        user = await repo.set_selected_date(callback.from_user.id, None)
        await session.commit()
    city = user.city_slug if user else "moscow"
    await callback.message.edit_text(main_menu_text(city, None), reply_markup=main_menu_keyboard())
    await callback.answer("Дата сброшена")


@router.callback_query(F.data == "date:noop")
async def date_noop(callback: CallbackQuery) -> None:
    await callback.answer()

