from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.formatters.events import EVENT_MESSAGE_PARSE_MODE
from src.bot.formatters.survey_card import format_survey_card
from src.bot.keyboards.survey import empty_result_keyboard, result_keyboard
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.models import Event
from src.storage.repositories.users import UserSettingsRepository


async def _selected_date_for_user(user_id: int):
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user = await UserSettingsRepository(session).get(user_id)
        return user.selected_date if user else None


async def show_survey_event(
    callback: CallbackQuery,
    state: FSMContext,
    event: Event,
    *,
    preface: str | None = None,
) -> None:
    data = await state.get_data()
    shown = list(data.get("shown_event_ids", []))
    if event.id not in shown:
        shown.append(event.id)
    source_slug = getattr(getattr(event, "source", None), "slug", None)
    await state.update_data(
        shown_event_ids=shown,
        current_event_id=event.id,
        current_source_slug=source_slug,
    )
    await state.set_state(BotStates.SURVEY_RESULT)

    selected_date = await _selected_date_for_user(callback.from_user.id)
    text = format_survey_card(
        event,
        audience=data.get("audience", "solo"),
        budget=data.get("budget", "unlimited"),
        selected_date=selected_date,
    )
    if preface:
        text = f"{preface}\n\n{text}"
    await _send_card(callback, text, result_keyboard(event.id))


async def show_viewing_event(
    callback: CallbackQuery,
    state: FSMContext,
    event: Event,
) -> None:
    from src.bot.formatters.survey_card import format_simple_card

    data = await state.get_data()
    shown = list(data.get("shown_event_ids", []))
    if event.id not in shown:
        shown.append(event.id)
    source_slug = getattr(getattr(event, "source", None), "slug", None)
    await state.update_data(
        shown_event_ids=shown,
        current_event_id=event.id,
        current_source_slug=source_slug,
    )
    await state.set_state(BotStates.VIEWING_EVENT)

    selected_date = await _selected_date_for_user(callback.from_user.id)
    text = format_simple_card(event, selected_date=selected_date)
    await _send_card(callback, text, result_keyboard(event.id))


async def _send_card(callback: CallbackQuery, text: str, reply_markup) -> None:  # type: ignore[no-untyped-def]
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=EVENT_MESSAGE_PARSE_MODE,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode=EVENT_MESSAGE_PARSE_MODE,
            disable_web_page_preview=True,
        )
    await callback.answer()


async def show_empty_with_fallback(
    callback: CallbackQuery,
    *,
    message: str,
) -> None:
    try:
        await callback.message.edit_text(message, reply_markup=empty_result_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(message, reply_markup=empty_result_keyboard())
    await callback.answer()
