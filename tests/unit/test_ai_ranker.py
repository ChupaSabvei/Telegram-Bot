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
        RankRequest(query="что-то интересное", city_slug="moscow", candidates=make_candidates())
    )
    assert result.event_ids == []
    assert result.clarification_needed
    assert result.clarification_message == "Уточните запрос"
    assert not result.fallback_used


@pytest.mark.asyncio
async def test_ai_ranker_fallback_path() -> None:
    ranker = AIRanker(llm_client=FailingClient())  # type: ignore[arg-type]
    result = await ranker.rank(
        RankRequest(query="джаз концерт", city_slug="moscow", candidates=make_candidates())
    )
    assert result.fallback_used
    assert "1" in result.event_ids
