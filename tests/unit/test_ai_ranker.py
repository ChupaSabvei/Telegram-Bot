from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.ai.ranker import AIRanker, EventCandidate, RankRequest


class HappyClient:
    async def rank(self, query: str, candidates: list[dict]):  # noqa: ARG002
        class R:
            event_ids = [candidates[0]["id"]]
            clarification_needed = False
            clarification_message = None

        return R()


class ClarifyClient:
    async def rank(self, query: str, candidates: list[dict]):  # noqa: ARG002
        class R:
            event_ids = []
            clarification_needed = True
            clarification_message = "Уточните запрос"

        return R()


class FailingClient:
    async def rank(self, query: str, candidates: list[dict]):  # noqa: ARG002
        raise RuntimeError("LLM down")


def make_candidates() -> list[EventCandidate]:
    now = datetime.now(tz=UTC)
    return [
        EventCandidate(
            id="1",
            title="Джазовый концерт",
            description="Музыка и импровизация",
            category_slug="concerts",
            start_at=now + timedelta(days=2),
            venue="Клуб",
            price_text="от 1000 ₽",
        ),
        EventCandidate(
            id="2",
            title="Театральная постановка",
            description="Классика",
            category_slug="theater",
            start_at=now + timedelta(days=3),
            venue="Театр",
            price_text="от 800 ₽",
        ),
    ]


@pytest.mark.asyncio
async def test_ai_ranker_happy_path() -> None:
    ranker = AIRanker(llm_client=HappyClient())  # type: ignore[arg-type]
    result = await ranker.rank(RankRequest(query="джаз", city_slug="moscow", candidates=make_candidates()))
    assert result.event_ids == ["1"]
    assert not result.clarification_needed
    assert not result.fallback_used


@pytest.mark.asyncio
async def test_ai_ranker_clarification_path() -> None:
    ranker = AIRanker(llm_client=ClarifyClient())  # type: ignore[arg-type]
    result = await ranker.rank(
        RankRequest(query="??", city_slug="moscow", candidates=make_candidates())
    )
    assert result.event_ids == []
    assert result.clarification_needed
    assert not result.fallback_used


@pytest.mark.asyncio
async def test_ai_ranker_fallback_broad_query() -> None:
    ranker = AIRanker(llm_client=FailingClient())  # type: ignore[arg-type]
    result = await ranker.rank(
        RankRequest(
            query="чем заняться в городе",
            city_slug="moscow",
            candidates=make_candidates(),
        )
    )
    assert result.fallback_used
    assert result.event_ids
    assert not result.clarification_needed


@pytest.mark.asyncio
async def test_ai_ranker_fallback_weekend_broad_query() -> None:
    now = datetime.now(tz=UTC)
    days_until_saturday = (5 - now.weekday()) % 7
    saturday = now + timedelta(days=days_until_saturday)
    sunday = saturday + timedelta(days=1)
    candidates = [
        EventCandidate(
            id="weekend-1",
            title="Концерт на выходных",
            description="Музыка",
            category_slug="concerts",
            start_at=saturday.replace(hour=19, minute=0, second=0, microsecond=0),
            venue="Клуб",
            price_text="от 1000 ₽",
        ),
        EventCandidate(
            id="weekday-1",
            title="Лекция в будни",
            description="Образование",
            category_slug="education",
            start_at=now + timedelta(days=10),
            venue="Центр",
            price_text="бесплатно",
        ),
    ]
    ranker = AIRanker(llm_client=FailingClient())  # type: ignore[arg-type]
    result = await ranker.rank(
        RankRequest(
            query="Найди в москве чем заняться на этих выходных",
            city_slug="moscow",
            candidates=candidates,
        )
    )
    assert result.fallback_used
    assert result.event_ids == ["weekend-1"]
    assert not result.clarification_needed
