from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from src.bot.services import ai_discovery
from src.bot.services.ai_discovery import (
    _alternative_candidates,
    discover_for_survey,
    survey_alternative_preface,
    survey_alternative_query,
)
from src.bot.services.survey_matcher import (
    SurveyFilters,
    event_matches_filters_except_activity,
)
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


async def _seed(
    repo: EventRepository,
    *,
    title: str,
    source_url: str,
    activity_slug: str,
    price_type: str = "free",
    venue_format: str = "indoor",
) -> str:
    event = await repo.upsert_event(
        EventDTO(
            source_url=source_url,
            source_slug="kudago",
            title=title,
            description="test",
            category_slug="other",
            activity_slug=activity_slug,  # type: ignore[arg-type]
            city_slug="moscow",
            venue="Площадка",
            start_at=datetime.now(tz=UTC) + timedelta(days=5),
            price_type=price_type,  # type: ignore[arg-type]
            venue_format=venue_format,  # type: ignore[arg-type]
        )
    )
    return event.id


def test_survey_alternative_query_mentions_other_categories() -> None:
    query = survey_alternative_query(
        SurveyFilters(
            city_slug="moscow",
            audience="solo",
            activity="sport",
            budget="1000",
            exclude_ids=[],
        )
    )
    assert "спорт" in query.lower()
    assert "других" in query.lower()


def test_survey_alternative_preface_uses_activity_label() -> None:
    preface = survey_alternative_preface(
        SurveyFilters(
            city_slug="moscow",
            audience="solo",
            activity="sport",
            budget="unlimited",
            exclude_ids=[],
        )
    )
    assert "Спорт" in preface
    assert "альтернатив" in preface.lower()


@pytest.mark.asyncio
async def test_discover_for_survey_calls_ai_for_alternatives(db_runtime, monkeypatch) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        culture_id = await _seed(
            repo,
            title="Концерт",
            source_url="https://example.com/alt/culture",
            activity_slug="culture",
        )
        await session.commit()

    captured: dict = {}

    async def fake_discover_by_query(session, *, query, city_slug, **kwargs):  # type: ignore[no-untyped-def]
        captured["query"] = query
        captured["candidates"] = kwargs.get("candidate_events")
        return ai_discovery.DiscoveryResult(events=[kwargs["candidate_events"][0]])

    monkeypatch.setattr(ai_discovery, "discover_by_query", fake_discover_by_query)

    async with db_runtime.session_factory() as session:
        result = await discover_for_survey(
            session,
            SurveyFilters(
                city_slug="moscow",
                audience="solo",
                activity="sport",
                budget="unlimited",
                exclude_ids=[],
            ),
        )

    assert result.events
    assert result.events[0].id == culture_id
    assert result.preface is not None
    assert "Спорт" in result.preface
    assert "других" in captured["query"].lower()
    assert all(item.activity_slug != "sport" for item in captured["candidates"])


@pytest.mark.asyncio
async def test_discover_for_survey_uses_strict_match_when_available(db_runtime, monkeypatch) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        sport_id = await _seed(
            repo,
            title="Футбол",
            source_url="https://example.com/alt/sport",
            activity_slug="sport",
        )
        await session.commit()

    captured: dict = {}

    async def fake_discover_by_query(session, *, query, city_slug, **kwargs):  # type: ignore[no-untyped-def]
        captured["query"] = query
        return ai_discovery.DiscoveryResult(events=[kwargs["candidate_events"][0]])

    monkeypatch.setattr(ai_discovery, "discover_by_query", fake_discover_by_query)

    async with db_runtime.session_factory() as session:
        result = await discover_for_survey(
            session,
            SurveyFilters(
                city_slug="moscow",
                audience="solo",
                activity="sport",
                budget="unlimited",
                exclude_ids=[],
            ),
        )

    assert result.events[0].id == sport_id
    assert "спорт" in captured["query"].lower()
    assert result.preface is None


@pytest.mark.asyncio
async def test_alternative_candidates_prefers_matching_budget(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await _seed(
            repo,
            title="Дорогое",
            source_url="https://example.com/alt/expensive",
            activity_slug="culture",
            price_type="paid",
        )
        cheap_id = await _seed(
            repo,
            title="Бесплатное",
            source_url="https://example.com/alt/free",
            activity_slug="culture",
            price_type="free",
        )
        await session.commit()

        pool = await repo.list_candidates_for_ai("moscow")
        filters = SurveyFilters(
            city_slug="moscow",
            audience="solo",
            activity="sport",
            budget="free",
            exclude_ids=[],
        )
        alternatives = _alternative_candidates(pool, filters)

    assert len(alternatives) == 1
    assert alternatives[0].id == cheap_id


def test_event_matches_filters_except_activity() -> None:
    from src.storage.models import Event

    event = Event(
        id="1",
        activity_slug="culture",
        price_type="free",
        venue_format="indoor",
        audience_tags=[],
    )
    filters = SurveyFilters(
        city_slug="moscow",
        audience="solo",
        activity="sport",
        budget="free",
        exclude_ids=[],
    )
    assert event_matches_filters_except_activity(event, filters) is True

    same_activity = Event(
        id="2",
        activity_slug="sport",
        price_type="free",
        venue_format="indoor",
        audience_tags=[],
    )
    assert event_matches_filters_except_activity(same_activity, filters) is False
