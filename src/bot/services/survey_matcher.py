from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.scrapers.event_dates import selected_date_range_utc
from src.storage.models import Event
from src.storage.repositories.events import EventRepository

Audience = Literal["solo", "couple", "family", "friends"]
Activity = Literal["sport", "kids", "family", "culture", "gastro", "relax"]
Budget = Literal["free", "1000", "3000", "unlimited"]

AUDIENCE_MAP: dict[Audience, set[str]] = {
    "solo": set(),
    "couple": set(),
    "family": {"family", "kids"},
    "friends": set(),
}


@dataclass(slots=True)
class SurveyFilters:
    city_slug: str
    audience: Audience
    activity: Activity
    budget: Budget
    exclude_ids: list[str]
    selected_date: date | None = None


@dataclass(slots=True)
class MatchResult:
    event: Event | None
    candidates_remaining: int
    relaxed: bool = False


def upgrade_budget(budget: Budget) -> Budget | None:
    order: list[Budget] = ["free", "1000", "3000", "unlimited"]
    try:
        idx = order.index(budget)
    except ValueError:
        return None
    if idx >= len(order) - 1:
        return None
    return order[idx + 1]


def _budget_match(event: Event, budget: Budget) -> bool:
    if budget == "unlimited":
        return True
    if budget == "free":
        return event.price_type == "free"
    limit = int(budget)
    return event.price_type == "free" or event.price_amount_rub is None or event.price_amount_rub <= limit


def _audience_match(event: Event, filters: SurveyFilters) -> bool:
    required = AUDIENCE_MAP.get(filters.audience, set())
    if not required:
        return True
    tags = set(event.audience_tags or [])
    if not tags:
        return True
    return bool(tags & required)


def event_matches_filters(event: Event, filters: SurveyFilters) -> bool:
    if event.activity_slug != filters.activity:
        return False
    if not _budget_match(event, filters.budget):
        return False
    return _audience_match(event, filters)


def event_matches_filters_except_activity(event: Event, filters: SurveyFilters) -> bool:
    if event.activity_slug == filters.activity:
        return False
    if not _budget_match(event, filters.budget):
        return False
    return _audience_match(event, filters)


class SurveyMatcher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_query(self, filters: SurveyFilters) -> Select[tuple[Event]]:
        now = datetime.now(tz=UTC)
        if filters.selected_date:
            day_start, day_end = selected_date_range_utc(filters.selected_date)
        else:
            day_start = now
            day_end = now + timedelta(days=30)
        query = (
            select(Event)
            .where(
                Event.city_slug == filters.city_slug,
                Event.start_at >= day_start,
                Event.start_at < day_end,
                Event.activity_slug == filters.activity,
            )
            .options(joinedload(Event.category), joinedload(Event.source))
        )
        if filters.selected_date:
            query = query.where(Event.start_at_confirmed.is_(True))
        if filters.exclude_ids:
            query = query.where(Event.id.not_in(filters.exclude_ids))
        return query

    def _apply_budget(self, query: Select[tuple[Event]], budget: Budget) -> Select[tuple[Event]]:
        if budget == "unlimited":
            return query
        if budget == "free":
            return query.where(Event.price_type == "free")
        limit = int(budget)
        return query.where(
            or_(
                Event.price_type == "free",
                Event.price_amount_rub.is_(None),
                Event.price_amount_rub <= limit,
            )
        )

    def _social_visibility_kwargs(self, filters: SurveyFilters) -> dict[str, object]:
        if filters.selected_date:
            day_start, day_end = selected_date_range_utc(filters.selected_date)
            return {"start": day_start, "end": day_end, "active_window": False}
        return {"start": None, "end": None, "active_window": True}

    async def count_candidates(self, filters: SurveyFilters) -> int:
        repo = EventRepository(self.session)
        query = self._apply_budget(self._base_query(filters), filters.budget)
        query = await repo.apply_social_visibility(
            query, filters.city_slug, **self._social_visibility_kwargs(filters)
        )
        query = repo._apply_publishable_filter(query)
        result = await self.session.scalars(query)
        return len([e for e in result if _audience_match(e, filters)])

    async def match(self, filters: SurveyFilters) -> MatchResult:
        repo = EventRepository(self.session)
        current = filters
        candidates: list[Event] = []
        for _ in range(4):
            candidates = await self._fetch_candidates(repo, current)
            if candidates:
                break
            upgraded = upgrade_budget(current.budget)
            if upgraded is None:
                break
            current = SurveyFilters(
                city_slug=current.city_slug,
                audience=current.audience,
                activity=current.activity,
                budget=upgraded,
                exclude_ids=current.exclude_ids,
                selected_date=current.selected_date,
            )
        if not candidates and filters.selected_date and filters.exclude_ids:
            no_exclude = SurveyFilters(
                city_slug=filters.city_slug,
                audience=filters.audience,
                activity=filters.activity,
                budget=filters.budget,
                exclude_ids=[],
                selected_date=filters.selected_date,
            )
            candidates = await self._fetch_candidates(repo, no_exclude)
        if not candidates:
            return MatchResult(event=None, candidates_remaining=0)
        event = candidates[0]
        remaining = max(0, len(candidates) - 1)
        return MatchResult(event=event, candidates_remaining=remaining)

    async def _fetch_candidates(self, repo: EventRepository, filters: SurveyFilters) -> list[Event]:
        query = self._apply_budget(self._base_query(filters), filters.budget)
        query = await repo.apply_social_visibility(
            query, filters.city_slug, **self._social_visibility_kwargs(filters)
        )
        query = repo._apply_publishable_filter(query)
        query = query.order_by(func.random()).limit(120)
        matched = [e for e in await self.session.scalars(query) if _audience_match(e, filters)]
        interleaved = EventRepository._interleave_by_source(matched, limit=50)
        random.shuffle(interleaved)
        return interleaved
