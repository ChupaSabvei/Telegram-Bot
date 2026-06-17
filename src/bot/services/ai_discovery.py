from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import OpenAIClient
from src.ai.ranker import AIRanker, EventCandidate, RankRequest
from src.bot.services.survey_matcher import (
    SurveyFilters,
    event_matches_filters,
    event_matches_filters_except_activity,
)
from src.config import get_config
from src.storage.models import Event
from src.storage.repositories.events import EventRepository

ACTIVITY_QUERIES = {
    "sport": "спортивное мероприятие",
    "kids": "мероприятие для детей",
    "family": "семейный отдых",
    "culture": "культурное мероприятие",
    "gastro": "гастрономия ресторан дегустация",
    "relax": "релакс спа йога",
}

ACTIVITY_LABELS = {
    "sport": "Спорт",
    "kids": "Для детей",
    "family": "Семейный отдых",
    "culture": "Культура",
    "gastro": "Гастро",
    "relax": "Релакс",
}

AUDIENCE_QUERIES = {
    "solo": "для одного",
    "couple": "для пары",
    "family": "для семьи с детьми",
    "friends": "для компании друзей",
}

BUDGET_QUERIES = {
    "free": "бесплатно",
    "1000": "до 1000 рублей",
    "3000": "до 3000 рублей",
    "unlimited": "любой бюджет",
}

AI_STILL_EMPTY = (
    "😔 По вашим фильтрам ничего не нашлось.\n"
    "Попробуйте смягчить фильтры, начать опрос заново или опишите запрос текстом."
)


@dataclass(slots=True)
class DiscoveryResult:
    events: list[Event]
    preface: str | None = None
    clarification: str | None = None


def survey_filters_to_query(filters: SurveyFilters) -> str:
    parts = [
        ACTIVITY_QUERIES.get(filters.activity, filters.activity),
        AUDIENCE_QUERIES.get(filters.audience, filters.audience),
        BUDGET_QUERIES.get(filters.budget, filters.budget),
    ]
    return " ".join(part for part in parts if part)


def survey_alternative_preface(filters: SurveyFilters) -> str:
    label = ACTIVITY_LABELS.get(filters.activity, filters.activity)
    return (
        f"😔 По категории «{label}» сейчас ничего не нашлось.\n"
        "Ниже — альтернативы из других категорий под ваши ответы:"
    )


def survey_alternative_query(filters: SurveyFilters) -> str:
    activity_label = ACTIVITY_LABELS.get(filters.activity, filters.activity)
    parts = [
        AUDIENCE_QUERIES.get(filters.audience, filters.audience),
        BUDGET_QUERIES.get(filters.budget, filters.budget),
    ]
    context = " ".join(part for part in parts if part)
    return (
        f"Пользователь искал «{activity_label}», но таких мероприятий нет. "
        f"Подбери альтернативы из ДРУГИХ категорий активности. {context}"
    ).strip()


def _alternative_candidates(pool: list[Event], filters: SurveyFilters) -> list[Event]:
    strict = [item for item in pool if event_matches_filters_except_activity(item, filters)]
    if strict:
        return strict
    return [item for item in pool if item.activity_slug != filters.activity]


def _to_candidates(events: list[Event]) -> list[EventCandidate]:
    return [
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
        for item in events
    ]


async def discover_by_query(
    session: AsyncSession,
    *,
    query: str,
    city_slug: str,
    exclude_ids: list[str] | None = None,
    candidate_events: list[Event] | None = None,
    selected_date: date | None = None,
) -> DiscoveryResult:
    repo = EventRepository(session)
    candidates = candidate_events or await repo.list_candidates_for_ai(
        city_slug,
        selected_date=selected_date,
    )
    if exclude_ids:
        excluded = set(exclude_ids)
        candidates = [item for item in candidates if item.id not in excluded]
    if not candidates:
        return DiscoveryResult(
            events=[],
            clarification="Пока нет мероприятий в вашем городе. Попробуйте позже или смените город.",
        )

    cfg = get_config()
    llm_client = OpenAIClient(
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        base_url=cfg.openai_api_base,
    )
    response = await AIRanker(llm_client).rank(
        RankRequest(query=query, city_slug=city_slug, candidates=_to_candidates(candidates))
    )
    if response.clarification_needed and not response.event_ids:
        return DiscoveryResult(events=[], clarification=response.clarification_message)

    event_ids = [str(event_id) for event_id in response.event_ids]
    events = await repo.get_by_ids(event_ids)
    if not events:
        return DiscoveryResult(
            events=[],
            clarification=response.clarification_message
            or "Не нашёл подходящих мероприятий. Попробуйте другую формулировку.",
        )

    return DiscoveryResult(events=events, preface=response.preface_message)


async def discover_for_survey(
    session: AsyncSession,
    filters: SurveyFilters,
) -> DiscoveryResult:
    repo = EventRepository(session)
    pool = await repo.list_candidates_for_ai(
        filters.city_slug,
        limit=200,
        selected_date=filters.selected_date,
    )
    if filters.exclude_ids:
        excluded = set(filters.exclude_ids)
        pool = [item for item in pool if item.id not in excluded]
    filtered = [item for item in pool if event_matches_filters(item, filters)]
    if filtered:
        return await discover_by_query(
            session,
            query=survey_filters_to_query(filters),
            city_slug=filters.city_slug,
            candidate_events=filtered,
            selected_date=filters.selected_date,
        )

    alternatives = _alternative_candidates(pool, filters)
    if not alternatives:
        return DiscoveryResult(events=[], clarification=AI_STILL_EMPTY)

    result = await discover_by_query(
        session,
        query=survey_alternative_query(filters),
        city_slug=filters.city_slug,
        candidate_events=alternatives,
        selected_date=filters.selected_date,
    )
    result.events = [item for item in result.events if item.activity_slug != filters.activity]
    if not result.events:
        return DiscoveryResult(events=[], clarification=AI_STILL_EMPTY)

    if not result.preface:
        result.preface = survey_alternative_preface(filters)
    return result
