from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rapidfuzz import fuzz

from src.ai.client import OpenAIClient
from src.ai.prompts import PROMPT_VERSION

logger = logging.getLogger(__name__)

MAX_LLM_CANDIDATES = 25
MAX_DESCRIPTION_LEN = 120

WEEKEND_KEYWORDS = ("выходн", "weekend", "суббот", "воскресен")
BROAD_QUERY_KEYWORDS = (
    "чем заня",
    "куда сход",
    "что посмот",
    "что интерес",
    "чем занят",
    "найди",
    "подбери",
    "посоветуй",
    "что делать",
)

@dataclass(slots=True)
class EventCandidate:
    id: str
    title: str
    description: str | None
    category_slug: str
    start_at: datetime
    venue: str | None
    price_text: str | None


@dataclass(slots=True)
class RankRequest:
    query: str
    city_slug: str
    candidates: list[EventCandidate]


@dataclass(slots=True)
class RankResponse:
    event_ids: list[str]
    clarification_needed: bool
    clarification_message: str | None
    prompt_version: str
    fallback_used: bool
    preface_message: str | None = None


class AIRanker:
    def __init__(self, llm_client: OpenAIClient) -> None:
        self.llm_client = llm_client

    async def rank(self, req: RankRequest) -> RankResponse:
        if len(req.query.strip()) < 3:
            return RankResponse(
                event_ids=[],
                clarification_needed=True,
                clarification_message="Уточните, пожалуйста: какой тип мероприятия или дату вы ищете?",
                prompt_version=PROMPT_VERSION,
                fallback_used=False,
            )

        if not req.candidates:
            return RankResponse(
                event_ids=[],
                clarification_needed=True,
                clarification_message="Пока нет мероприятий в вашем городе. Попробуйте позже или смените город.",
                prompt_version=PROMPT_VERSION,
                fallback_used=False,
            )

        llm_candidates = self._select_llm_candidates(req)

        try:
            llm_result = await self.llm_client.rank(
                query=req.query,
                candidates=self._compact_for_llm(llm_candidates),
            )
            ids = [item.id for item in req.candidates]
            filtered = [event_id for event_id in llm_result.event_ids if event_id in ids][:10]
            if filtered:
                return RankResponse(
                    event_ids=filtered,
                    clarification_needed=False,
                    clarification_message=None,
                    prompt_version=PROMPT_VERSION,
                    fallback_used=False,
                )
            if llm_result.clarification_needed:
                fallback = self._fallback_rank(req=req)
                if fallback:
                    return RankResponse(
                        event_ids=fallback[:10],
                        clarification_needed=False,
                        clarification_message=None,
                        preface_message="Точного совпадения не нашёл, но вот подборка из афиши:",
                        prompt_version=PROMPT_VERSION,
                        fallback_used=True,
                    )
                return RankResponse(
                    event_ids=[],
                    clarification_needed=True,
                    clarification_message=_friendly_clarification(req.query),
                    prompt_version=PROMPT_VERSION,
                    fallback_used=False,
                )
        except Exception as exc:
            logger.warning("LLM rank failed, using fallback: %s", exc)

        fallback = self._fallback_rank(req=req)
        if not fallback:
            return RankResponse(
                event_ids=[],
                clarification_needed=True,
                clarification_message=_friendly_clarification(req.query),
                prompt_version=PROMPT_VERSION,
                fallback_used=True,
            )
        return RankResponse(
            event_ids=fallback[:10],
            clarification_needed=False,
            clarification_message=None,
            preface_message="Точного совпадения не нашёл, но вот подборка из афиши:",
            prompt_version=PROMPT_VERSION,
            fallback_used=True,
        )

    def _select_llm_candidates(self, req: RankRequest) -> list[EventCandidate]:
        candidates = list(req.candidates)
        if _is_weekend_query(req.query):
            weekend_days = _upcoming_weekend_days(datetime.now(tz=UTC))
            weekend_events = [item for item in candidates if item.start_at.date() in weekend_days]
            if weekend_events:
                candidates = weekend_events

        if _is_broad_query(req.query):
            return _diverse_sample(candidates, limit=MAX_LLM_CANDIDATES)

        scored = self._score_candidates(req.query, candidates)
        if scored:
            return [item for item, _ in scored[:MAX_LLM_CANDIDATES]]
        return candidates[:MAX_LLM_CANDIDATES]

    def _compact_for_llm(self, candidates: list[EventCandidate]) -> list[dict]:
        compact: list[dict] = []
        for item in candidates:
            description = (item.description or "").strip()
            if len(description) > MAX_DESCRIPTION_LEN:
                description = f"{description[: MAX_DESCRIPTION_LEN - 1]}…"
            compact.append(
                {
                    "id": item.id,
                    "title": item.title[:100],
                    "description": description or None,
                    "category_slug": item.category_slug,
                    "start_at": item.start_at.strftime("%Y-%m-%d %H:%M"),
                    "venue": (item.venue or "")[:60] or None,
                    "price_text": (item.price_text or "")[:40] or None,
                }
            )
        return compact

    def _fallback_rank(self, req: RankRequest) -> list[str]:
        query = req.query.lower().strip()
        if _is_weekend_query(query) or _is_broad_query(query):
            weekend_ids = self._weekend_event_ids(req.candidates)
            if weekend_ids:
                return weekend_ids
            return [item.id for item in sorted(req.candidates, key=lambda x: x.start_at)[:10]]

        scored = self._score_candidates(query, req.candidates, min_score=30)
        return [event_id for event_id, _ in scored]

    def _weekend_event_ids(self, candidates: list[EventCandidate]) -> list[str]:
        weekend_days = _upcoming_weekend_days(datetime.now(tz=UTC))
        weekend_events = sorted(
            (item for item in candidates if item.start_at.date() in weekend_days),
            key=lambda item: item.start_at,
        )
        return [item.id for item in _diverse_sample(weekend_events, limit=10)]

    def _score_candidates(
        self,
        query: str,
        candidates: list[EventCandidate],
        min_score: float = 40,
    ) -> list[tuple[EventCandidate, float]]:
        scored: list[tuple[EventCandidate, float]] = []
        for item in candidates:
            content = " ".join([item.title, item.description or "", item.category_slug]).lower()
            score = fuzz.token_set_ratio(query, content)
            if score >= min_score:
                scored.append((item, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored


def _is_weekend_query(query: str) -> bool:
    lowered = query.lower()
    return any(keyword in lowered for keyword in WEEKEND_KEYWORDS)


def _is_broad_query(query: str) -> bool:
    lowered = query.lower()
    return any(keyword in lowered for keyword in BROAD_QUERY_KEYWORDS)


def _friendly_clarification(query: str) -> str:  # noqa: ARG001
    return (
        "Не нашёл подходящих событий по этому запросу.\n"
        "Попробуйте конкретнее: «джаз в субботу», «спектакль для детей» "
        "или выберите категорию в меню."
    )


def _upcoming_weekend_days(now: datetime) -> set[datetime.date]:
    weekday = now.weekday()
    days_until_saturday = (5 - weekday) % 7
    if weekday == 5:
        days_until_saturday = 0
    if weekday == 6:
        days_until_saturday = 6
    saturday = (now + timedelta(days=days_until_saturday)).date()
    sunday = saturday + timedelta(days=1)
    return {saturday, sunday}


def _diverse_sample(candidates: list[EventCandidate], limit: int) -> list[EventCandidate]:
    if len(candidates) <= limit:
        return candidates

    picked: list[EventCandidate] = []
    seen_categories: set[str] = set()
    for item in sorted(candidates, key=lambda candidate: candidate.start_at):
        if item.category_slug in seen_categories:
            continue
        picked.append(item)
        seen_categories.add(item.category_slug)
        if len(picked) >= limit:
            return picked

    for item in sorted(candidates, key=lambda candidate: candidate.start_at):
        if item in picked:
            continue
        picked.append(item)
        if len(picked) >= limit:
            break
    return picked
