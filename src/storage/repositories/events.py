from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from rapidfuzz import fuzz
from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.storage.models import Category, Event, EventSource
from src.storage.schemas import EventDTO


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_category_id(self, category_slug: str) -> str:
        category_id = await self.session.scalar(
            select(Category.id).where(Category.slug == category_slug)
        )
        if category_id is None:
            raise ValueError(f"Unknown category slug: {category_slug}")
        return category_id

    async def get_source_id(self, source_slug: str) -> str:
        source_id = await self.session.scalar(
            select(EventSource.id).where(EventSource.slug == source_slug)
        )
        if source_id is None:
            raise ValueError(f"Unknown source slug: {source_slug}")
        return source_id

    def _active_window_query(self) -> Select[tuple[Event]]:
        now = datetime.now(tz=UTC)
        horizon = now + timedelta(days=30)
        return select(Event).where(
            and_(
                Event.start_at > now,
                Event.start_at <= horizon,
                Event.is_online.is_(False),
            )
        )

    async def list_by_city_category(self, city_slug: str, category_slug: str, limit: int = 10) -> list[Event]:
        category_id = await self.get_category_id(category_slug)
        query = (
            self._active_window_query()
            .where(and_(Event.city_slug == city_slug, Event.category_id == category_id))
            .order_by(Event.start_at.asc())
            .limit(limit)
            .options(joinedload(Event.category), joinedload(Event.source))
        )
        result = await self.session.scalars(query)
        return list(result)

    async def list_candidates_for_ai(self, city_slug: str, limit: int = 100) -> list[Event]:
        query = (
            self._active_window_query()
            .where(Event.city_slug == city_slug)
            .order_by(Event.start_at.asc())
            .limit(limit)
            .options(joinedload(Event.category), joinedload(Event.source))
        )
        result = await self.session.scalars(query)
        return list(result)

    async def get_by_ids(self, event_ids: list[str]) -> list[Event]:
        if not event_ids:
            return []
        query = select(Event).where(Event.id.in_(event_ids)).options(
            joinedload(Event.category), joinedload(Event.source)
        )
        result = await self.session.scalars(query)
        by_id = {item.id: item for item in result}
        return [by_id[event_id] for event_id in event_ids if event_id in by_id]

    async def _find_dedup_target(self, dto: EventDTO) -> Event | None:
        same_city_query = self._active_window_query().where(Event.city_slug == dto.city_slug)
        events = list(await self.session.scalars(same_city_query))
        for existing in events:
            same_day = existing.start_at.date() == dto.start_at.date()
            venue_score = fuzz.token_sort_ratio(existing.venue or "", dto.venue or "")
            title_score = fuzz.token_sort_ratio(existing.title, dto.title)
            if same_day and title_score >= 80 and venue_score >= 70:
                return existing
        return None

    async def upsert_event(self, dto: EventDTO) -> Event:
        existing = await self.session.scalar(select(Event).where(Event.source_url == str(dto.source_url)))
        category_id = await self.get_category_id(dto.category_slug)
        source_id = await self.get_source_id(dto.source_slug)

        dedup_target = await self._find_dedup_target(dto)
        dedup_group_id = dedup_target.dedup_group_id if dedup_target else None
        if dedup_target and dedup_group_id is None:
            dedup_group_id = str(uuid.uuid4())
            dedup_target.dedup_group_id = dedup_group_id
            await self.session.flush()

        if existing is None:
            existing = Event(
                source_id=source_id,
                external_id=dto.external_id,
                source_url=str(dto.source_url),
                dedup_group_id=dedup_group_id,
                title=dto.title,
                description=dto.description,
                category_id=category_id,
                city_slug=dto.city_slug,
                venue=dto.venue,
                start_at=dto.start_at,
                end_at=dto.end_at,
                price_type=dto.price_type,
                price_text=dto.price_text,
                is_online=False,
                image_url=str(dto.image_url) if dto.image_url else None,
                synced_at=datetime.now(tz=UTC),
            )
            self.session.add(existing)
        else:
            existing.source_id = source_id
            existing.external_id = dto.external_id
            existing.title = dto.title
            existing.description = dto.description
            existing.category_id = category_id
            existing.city_slug = dto.city_slug
            existing.venue = dto.venue
            existing.start_at = dto.start_at
            existing.end_at = dto.end_at
            existing.price_type = dto.price_type
            existing.price_text = dto.price_text
            existing.is_online = False
            existing.image_url = str(dto.image_url) if dto.image_url else None
            existing.synced_at = datetime.now(tz=UTC)
            if dedup_group_id:
                existing.dedup_group_id = dedup_group_id

        await self.session.flush()
        return existing
