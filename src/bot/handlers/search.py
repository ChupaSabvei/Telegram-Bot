from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.ai.client import OpenAIClient
from src.ai.intent import detect_search_mode, extract_place_topic
from src.ai.places import PlaceAdvisor
from src.ai.query_constraints import parse_query_constraints, upcoming_weekend_dates
from src.storage.event_times import event_on_any_of_dates
from src.ai.ranker import AIRanker, EventCandidate, RankRequest, _is_broad_query, _is_weekend_query
from src.bot.formatters.events import EVENT_MESSAGE_PARSE_MODE, format_event_list
from src.bot.formatters.places import format_places_response
from src.bot.keyboards.menus import category_keyboard, events_keyboard
from src.bot.states import BotStates
from src.config import get_config
from src.storage.database import build_runtime
from src.storage.repositories.events import EventRepository
from src.storage.repositories.users import UserSettingsRepository

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def search_events(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer("Пожалуйста, опишите запрос текстом.")
        return
    text = message.text.strip()
    if not text:
        await message.answer("Напишите запрос или напишите, что хотите посетить.")
        return
    if len(text) > 500:
        await message.answer("Запрос слишком длинный. Максимум 500 символов.")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        user_repo = UserSettingsRepository(session)
        event_repo = EventRepository(session)
        user = await user_repo.get(message.from_user.id)
        if user is None:
            await message.answer("Сначала выполните /start.")
            return

        cfg = get_config()
        llm_client = OpenAIClient(
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            base_url=cfg.openai_api_base,
        )

        if detect_search_mode(text) == "places":
            topic = extract_place_topic(text)
            places = await PlaceAdvisor(llm_client).recommend(
                query=text,
                city_slug=user.city_slug,
                topic=topic,
            )
            await state.set_state(BotStates.AI_SEARCH)
            await message.answer(
                format_places_response(places),
                parse_mode=EVENT_MESSAGE_PARSE_MODE,
                reply_markup=category_keyboard(),
            )
            return

        constraints = parse_query_constraints(text)
        if constraints.target_dates:
            candidates = await event_repo.list_candidates_for_ai(
                user.city_slug,
                limit=200,
            )
            candidates = [
                item
                for item in candidates
                if event_on_any_of_dates(item, set(constraints.target_dates))
            ]
        elif user.selected_date:
            candidates = await event_repo.list_candidates_for_ai(
                user.city_slug,
                selected_date=user.selected_date,
            )
        else:
            candidates = await event_repo.list_candidates_for_ai(
                user.city_slug,
                limit=200,
            )
        ranker = AIRanker(llm_client)
        req = RankRequest(
            query=text,
            city_slug=user.city_slug,
            candidates=[
                EventCandidate(
                    id=item.id,
                    title=item.title,
                    description=item.description,
                    category_slug=item.category.slug if item.category else "other",
                    start_at=item.start_at,
                    venue=item.venue,
                    price_text=item.price_text,
                    start_at_confirmed=getattr(item, "start_at_confirmed", True),
                )
                for item in candidates
            ],
        )
        response = await ranker.rank(req)
        if response.clarification_needed and not response.event_ids:
            await message.answer(
                response.clarification_message
                or "Уточните, пожалуйста: какой тип мероприятия или дату вы ищете?",
                reply_markup=category_keyboard(),
            )
            return

        events = await event_repo.get_by_ids(response.event_ids)
        if constraints.target_dates:
            target_dates = set(constraints.target_dates)
            events = [item for item in events if event_on_any_of_dates(item, target_dates)]
        if not events:
            await message.answer(
                "Не нашёл подходящих мероприятий в афише.\n"
                "Попробуйте другую формулировку или выберите категорию.",
                reply_markup=category_keyboard(),
            )
            return

        events = EventRepository._interleave_by_source(events, limit=len(events))

        header = response.preface_message or ""
        if header and not header.endswith("\n"):
            header += "\n\n"
        if not header and response.fallback_used and _is_weekend_query(text):
            weekend = sorted(upcoming_weekend_dates())
            if len(weekend) == 2:
                header = f"🗓 Подборка на выходные {weekend[0].strftime('%d.%m')}–{weekend[1].strftime('%d.%m')}:\n\n"
            elif weekend:
                header = f"🗓 Подборка на {weekend[0].strftime('%d.%m')}:\n\n"
            else:
                header = "🗓 Подборка на ближайшие выходные:\n\n"
        elif not header and response.fallback_used and _is_broad_query(text):
            header = "✨ Подборка мероприятий на ближайшие дни:\n\n"

        await state.update_data(
            last_list_ids=[event.id for event in events],
            last_category="other",
            ai_last_query_at=datetime.utcnow().isoformat(),
        )
        await state.set_state(BotStates.AI_SEARCH)
        await message.answer(
            header
            + format_event_list(events=events, category_slug="other", city_slug=user.city_slug),
            reply_markup=events_keyboard(
                [item.id for item in events],
                [item.title for item in events],
            ),
            parse_mode=EVENT_MESSAGE_PARSE_MODE,
        )
