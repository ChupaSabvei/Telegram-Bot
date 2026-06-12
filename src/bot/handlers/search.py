from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.ai.client import OpenAIClient
from src.ai.ranker import AIRanker, EventCandidate, RankRequest
from src.bot.formatters.events import format_event_list
from src.bot.keyboards.menus import events_keyboard
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
        await message.answer("Напишите запрос или выберите категорию.")
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

        candidates = await event_repo.list_candidates_for_ai(user.city_slug)
        cfg = get_config()
        ranker = AIRanker(OpenAIClient(api_key=cfg.openai_api_key))
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
                )
                for item in candidates
            ],
        )
        response = await ranker.rank(req)
        if response.clarification_needed and not response.event_ids:
            await message.answer(
                response.clarification_message
                or "Уточните, пожалуйста: какой тип мероприятия или дату вы ищете?"
            )
            return

        events = await event_repo.get_by_ids(response.event_ids)
        await state.update_data(
            last_list_ids=[event.id for event in events],
            last_category="other",
            ai_last_query_at=datetime.utcnow().isoformat(),
        )
        await state.set_state(BotStates.AI_SEARCH)
        await message.answer(
            format_event_list(events=events, category_slug="other", city_slug=user.city_slug),
            reply_markup=events_keyboard([item.id for item in events]) if events else None,
        )
