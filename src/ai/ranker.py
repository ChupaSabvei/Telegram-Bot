from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rapidfuzz import fuzz

from src.ai.client import OpenAIClient
from src.ai.prompts import PROMPT_VERSION


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

        try:
            llm_result = await self.llm_client.rank(
                query=req.query,
                candidates=[
                    {
                        "id": item.id,
                        "title": item.title,
                        "description": item.description,
                        "category_slug": item.category_slug,
                        "start_at": item.start_at.isoformat(),
                        "venue": item.venue,
                        "price_text": item.price_text,
                    }
                    for item in req.candidates
                ],
            )
            ids = [item.id for item in req.candidates]
            filtered = [event_id for event_id in llm_result.event_ids if event_id in ids][:10]
            return RankResponse(
                event_ids=filtered,
                clarification_needed=llm_result.clarification_needed,
                clarification_message=llm_result.clarification_message,
                prompt_version=PROMPT_VERSION,
                fallback_used=False,
            )
        except Exception:
            fallback = self._fallback_rank(req=req)
            if not fallback:
                return RankResponse(
                    event_ids=[],
                    clarification_needed=True,
                    clarification_message="Не удалось обработать запрос. Выберите категорию из меню.",
                    prompt_version=PROMPT_VERSION,
                    fallback_used=True,
                )
            return RankResponse(
                event_ids=fallback[:10],
                clarification_needed=False,
                clarification_message=None,
                prompt_version=PROMPT_VERSION,
                fallback_used=True,
            )

    def _fallback_rank(self, req: RankRequest) -> list[str]:
        query = req.query.lower().strip()
        scored: list[tuple[str, float]] = []
        for item in req.candidates:
            content = " ".join([item.title, item.description or "", item.category_slug]).lower()
            score = fuzz.token_set_ratio(query, content)
            if score >= 40:
                scored.append((item.id, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [event_id for event_id, _ in scored]
