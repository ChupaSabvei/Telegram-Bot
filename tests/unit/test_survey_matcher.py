from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from src.bot.services.survey_matcher import SurveyFilters, SurveyMatcher
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


async def _seed_event(
    repo: EventRepository,
    *,
    title: str,
    source_url: str,
    activity_slug: str,
    venue_format: str = "indoor",
    price_type: str = "paid",
    price_amount_rub: int | None = 1000,
    audience_tags: list[str] | None = None,
    is_online: bool = False,
    popularity_score: int = 0,
    days_ahead: int = 5,
    source_slug: str = "kudago",
    start_at: datetime | None = None,
) -> str:
    dto = EventDTO(
        source_url=source_url,
        source_slug=source_slug,  # type: ignore[arg-type]
        title=title,
        description="test",
        category_slug="other",
        activity_slug=activity_slug,  # type: ignore[arg-type]
        city_slug="moscow",
        venue="Площадка",
        start_at=start_at or datetime.now(tz=UTC) + timedelta(days=days_ahead),
        price_type=price_type,  # type: ignore[arg-type]
        price_amount_rub=price_amount_rub,
        venue_format=venue_format,  # type: ignore[arg-type]
        audience_tags=audience_tags or [],
        is_online=is_online,
        popularity_score=popularity_score,
    )
    event = await repo.upsert_event(dto)
    return event.id


@pytest.mark.asyncio
async def test_matcher_family_outdoor_budget_3000(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await _seed_event(
            repo,
            title="Семейный пикник",
            source_url="https://example.com/family/1",
            activity_slug="family",
            venue_format="outdoor",
            price_amount_rub=2500,
            audience_tags=["family"],
            popularity_score=10,
        )
        await _seed_event(
            repo,
            title="Дорогое семейное",
            source_url="https://example.com/family/2",
            activity_slug="family",
            venue_format="outdoor",
            price_amount_rub=5000,
            audience_tags=["family"],
        )
        await session.commit()

        matcher = SurveyMatcher(session)
        result = await matcher.match(
            SurveyFilters(
                city_slug="moscow",
                audience="family",
                activity="family",
                budget="3000",
                exclude_ids=[],
            )
        )

    assert result.event is not None
    assert result.event.title == "Семейный пикник"
    assert result.relaxed is False


@pytest.mark.asyncio
async def test_matcher_returns_matching_activity_without_format_filter(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        outdoor_id = await _seed_event(
            repo,
            title="Уличный фестиваль",
            source_url="https://example.com/outdoor/1",
            activity_slug="culture",
            venue_format="outdoor",
            popularity_score=100,
        )
        indoor_id = await _seed_event(
            repo,
            title="Клубный концерт",
            source_url="https://example.com/indoor/1",
            activity_slug="culture",
            venue_format="indoor",
            popularity_score=50,
        )
        await session.commit()

        matcher = SurveyMatcher(session)
        result = await matcher.match(
            SurveyFilters(
                city_slug="moscow",
                audience="solo",
                activity="culture",
                budget="unlimited",
                exclude_ids=[],
            )
        )

    assert result.event is not None
    assert result.event.id in {outdoor_id, indoor_id}


@pytest.mark.asyncio
async def test_matcher_excludes_shown_ids(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        first_id = await _seed_event(
            repo,
            title="Первое событие",
            source_url="https://example.com/culture/1",
            activity_slug="culture",
            popularity_score=100,
        )
        second_id = await _seed_event(
            repo,
            title="Второе событие",
            source_url="https://example.com/culture/2",
            activity_slug="culture",
            popularity_score=50,
        )
        await session.commit()

        matcher = SurveyMatcher(session)
        result = await matcher.match(
            SurveyFilters(
                city_slug="moscow",
                audience="solo",
                activity="culture",
                budget="unlimited",
                exclude_ids=[first_id],
            )
        )

    assert result.event is not None
    assert result.event.id == second_id


@pytest.mark.asyncio
async def test_matcher_empty_no_auto_relax(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        await _seed_event(
            repo,
            title="Спорт",
            source_url="https://example.com/sport/1",
            activity_slug="sport",
        )
        await session.commit()

        matcher = SurveyMatcher(session)
        result = await matcher.match(
            SurveyFilters(
                city_slug="moscow",
                audience="solo",
                activity="gastro",
                budget="free",
                exclude_ids=[],
            )
        )

    assert result.event is None
    assert result.candidates_remaining == 0
    assert result.relaxed is False


@pytest.mark.asyncio
async def test_matcher_selected_date_uses_moscow_day_boundaries(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        event_id = await _seed_event(
            repo,
            title="Ночной спорт",
            source_url="https://example.com/survey/date-msk",
            activity_slug="sport",
            start_at=datetime(2026, 6, 20, 22, 30, tzinfo=UTC),
        )
        await session.commit()

        matcher = SurveyMatcher(session)
        result = await matcher.match(
            SurveyFilters(
                city_slug="moscow",
                audience="solo",
                activity="sport",
                budget="unlimited",
                exclude_ids=[],
                selected_date=date(2026, 6, 21),
            )
        )

    assert result.event is not None
    assert result.event.id == event_id


@pytest.mark.asyncio
async def test_matcher_excludes_telegram_when_other_sources_have_data(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        kudago_id = await _seed_event(
            repo,
            title="KudaGo спорт",
            source_url="https://example.com/survey/kudago-only",
            activity_slug="sport",
            source_slug="kudago",
            popularity_score=20,
        )
        timepad_id = await _seed_event(
            repo,
            title="Timepad спорт",
            source_url="https://example.com/survey/timepad",
            activity_slug="sport",
            source_slug="timepad",
            popularity_score=10,
        )
        telegram_id = await _seed_event(
            repo,
            title="TG спорт",
            source_url="https://t.me/channel/sport",
            activity_slug="sport",
            source_slug="telegram_channels",
            popularity_score=100,
        )
        await session.commit()

        matcher = SurveyMatcher(session)
        result = await matcher.match(
            SurveyFilters(
                city_slug="moscow",
                audience="solo",
                activity="sport",
                budget="unlimited",
                exclude_ids=[],
            )
        )

    assert result.event is not None
    assert result.event.id in {kudago_id, timepad_id}
    assert result.event.id != telegram_id
