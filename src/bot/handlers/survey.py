from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.handlers.event_cards import show_empty_with_fallback, show_survey_event
from src.bot.handlers.navigation import open_main_menu
from src.bot.keyboards.survey import (
    activity_keyboard,
    audience_keyboard,
    budget_keyboard,
)
from src.bot.services.ai_discovery import AI_STILL_EMPTY, discover_for_survey
from src.bot.services.survey_matcher import SurveyFilters, SurveyMatcher, upgrade_budget
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.models import UserSettings
from src.storage.repositories.favorites import FavoritesRepository
from src.storage.repositories.users import UserSettingsRepository

router = Router()


async def _get_user(telegram_id: int) -> UserSettings | None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        return await UserSettingsRepository(session).get(telegram_id)


async def _load_filters(
    state: FSMContext,
    city_slug: str,
    selected_date,
) -> SurveyFilters | None:
    data = await state.get_data()
    audience = data.get("audience")
    activity = data.get("activity")
    budget = data.get("budget")
    if not all([audience, activity, budget]):
        return None
    shown_ids = data.get("shown_event_ids", [])
    return SurveyFilters(
        city_slug=city_slug,
        audience=audience,
        activity=activity,
        budget=budget,
        exclude_ids=shown_ids,
        selected_date=selected_date,
    )


@router.callback_query(F.data == "menu:survey")
async def start_survey(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BotStates.SURVEY_AUDIENCE)
    await state.update_data(shown_event_ids=[])
    await callback.message.edit_text("Кто идёт?", reply_markup=audience_keyboard())
    await callback.answer()


@router.callback_query(BotStates.SURVEY_AUDIENCE, F.data.startswith("survey:aud:"))
async def survey_audience(callback: CallbackQuery, state: FSMContext) -> None:
    audience = callback.data.split(":")[-1]
    await state.update_data(audience=audience)
    await state.set_state(BotStates.SURVEY_ACTIVITY)
    await callback.message.edit_text("Какая категория активности?", reply_markup=activity_keyboard())
    await callback.answer()


@router.callback_query(BotStates.SURVEY_ACTIVITY, F.data.startswith("survey:act:"))
async def survey_activity(callback: CallbackQuery, state: FSMContext) -> None:
    activity = callback.data.split(":")[-1]
    await state.update_data(activity=activity)
    await state.set_state(BotStates.SURVEY_BUDGET)
    await callback.message.edit_text("Какой бюджет?", reply_markup=budget_keyboard())
    await callback.answer()


@router.callback_query(BotStates.SURVEY_BUDGET, F.data.startswith("survey:bud:"))
async def survey_budget(callback: CallbackQuery, state: FSMContext) -> None:
    budget = callback.data.split(":")[-1]
    await state.update_data(budget=budget)
    await _show_match(callback, state)


async def _show_match(callback: CallbackQuery, state: FSMContext) -> None:
    user = await _get_user(callback.from_user.id)
    if user is None:
        await callback.answer("Сначала /start", show_alert=True)
        return
    filters = await _load_filters(state, user.city_slug, user.selected_date)
    if filters is None:
        await callback.answer("Опрос не завершён", show_alert=True)
        return

    runtime = build_runtime()
    async with runtime.session_factory() as session:
        matcher = SurveyMatcher(session)
        result = await matcher.match(filters)
        if result.event is not None:
            await show_survey_event(callback, state, result.event)
            return

        ai_result = await discover_for_survey(session, filters)

    if ai_result.events:
        await show_survey_event(
            callback,
            state,
            ai_result.events[0],
            preface=ai_result.preface,
        )
        return

    await state.set_state(BotStates.SURVEY_RESULT)
    message = ai_result.clarification or AI_STILL_EMPTY
    await show_empty_with_fallback(callback, message=message)


@router.callback_query(BotStates.SURVEY_RESULT, F.data == "result:next")
async def result_next(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_match(callback, state)


@router.callback_query(F.data.startswith("result:fav:"))
async def result_favorite(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = callback.data.split(":")[-1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        await FavoritesRepository(session).add(callback.from_user.id, event_id)
        await session.commit()
    await callback.answer("Сохранено в избранное ❤️")


@router.callback_query(BotStates.SURVEY_RESULT, F.data == "result:restart")
async def result_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await open_main_menu(callback, state)


@router.callback_query(F.data == "empty:budget")
async def empty_budget(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    new_budget = upgrade_budget(data.get("budget", "free"))
    if new_budget is None:
        await callback.answer("Бюджет уже максимальный")
        return
    await state.update_data(budget=new_budget)
    await _show_match(callback, state)


@router.callback_query(F.data == "empty:restart")
async def empty_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await start_survey(callback, state)
