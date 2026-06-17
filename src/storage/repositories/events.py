from __future__ import annotations

import random
import uuid
from datetime import UTC, date, datetime, timedelta

from rapidfuzz import fuzz
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.scrapers.event_dates import selected_date_range_utc
from src.scrapers.social_sources import SOCIAL_SOURCE_SLUGS, should_use_social_sources
from src.storage.event_filters import is_publishable_event_url
from src.storage.event_times import event_in_date_range
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

    @staticmethod
    def _date_range(selected_date: date | None) -> tuple[datetime | None, datetime | None]:
        if selected_date is None:
            return None, None
        return selected_date_range_utc(selected_date)

    async def _source_counts_for_city(
        self,
        city_slug: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        active_window: bool = False,
    ) -> dict[str, int]:
        query = (
            select(EventSource.slug, func.count(Event.id))
            .join(Event, Event.source_id == EventSource.id)
            .where(Event.city_slug == city_slug)
        )
        query = query.where(self._publishable_events_filter())
        if start is not None and end is not None:
            query = query.where(
                Event.start_at >= start,
                Event.start_at < end,
                Event.start_at_confirmed.is_(True),
            )
        elif active_window:
            now = datetime.now(tz=UTC)
            horizon = now + timedelta(days=30)
            query = query.where(Event.start_at > now, Event.start_at <= horizon)
        rows = await self.session.execute(query.group_by(EventSource.slug))
        return {slug: count for slug, count in rows.all()}

    async def social_sources_enabled(
        self,
        city_slug: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        active_window: bool = False,
    ) -> bool:
        counts = await self._source_counts_for_city(
            city_slug,
            start=start,
            end=end,
            active_window=active_window,
        )
        kudago_count = counts.get("kudago", 0)
        non_kudago_non_social_count = sum(
            count
            for source_slug, count in counts.items()
            if source_slug not in SOCIAL_SOURCE_SLUGS and source_slug != "kudago"
        )
        return should_use_social_sources(
            kudago_count=kudago_count,
            non_kudago_non_social_count=non_kudago_non_social_count,
        )

    async def _social_source_ids(self) -> list[str]:
        rows = await self.session.scalars(
            select(EventSource.id).where(EventSource.slug.in_(tuple(SOCIAL_SOURCE_SLUGS)))
        )
        return list(rows)

    async def apply_social_visibility(
        self,
        query: Select[tuple[Event]],
        city_slug: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        active_window: bool = False,
    ) -> Select[tuple[Event]]:
        if await self.social_sources_enabled(
            city_slug,
            start=start,
            end=end,
            active_window=active_window,
        ):
            return query
        social_ids = await self._social_source_ids()
        if not social_ids:
            return query
        return query.where(Event.source_id.not_in(social_ids))

    @staticmethod
    def _publishable_events_filter():
        clauses = []
        for part in ("/places/", "/collections/", "/venues/"):
            clauses.append(~Event.source_url.like(f"%{part}%"))
        return and_(*clauses)

    def _apply_publishable_filter(self, query: Select[tuple[Event]]) -> Select[tuple[Event]]:
        return query.where(self._publishable_events_filter())

    async def delete_unpublishable_events(self, city_slug: str, source_slug: str | None = None) -> int:
        query = select(Event).where(Event.city_slug == city_slug)
        if source_slug:
            source_id = await self.get_source_id(source_slug)
            query = query.where(Event.source_id == source_id)
        events = list(await self.session.scalars(query))
        deleted = 0
        for event in events:
            if not is_publishable_event_url(event.source_url):
                await self.session.delete(event)
                deleted += 1
        if deleted:
            await self.session.flush()
        return deleted

    async def prune_source_except_urls(
        self,
        city_slug: str,
        source_slug: str,
        keep_urls: set[str],
    ) -> int:
        if not keep_urls:
            return 0
        source_id = await self.get_source_id(source_slug)
        events = list(
            await self.session.scalars(
                select(Event).where(Event.city_slug == city_slug, Event.source_id == source_id)
            )
        )
        deleted = 0
        for event in events:
            if str(event.source_url) not in keep_urls:
                await self.session.delete(event)
                deleted += 1
        if deleted:
            await self.session.flush()
        return deleted

    async def delete_by_source_slug(self, city_slug: str, source_slug: str) -> int:
        source_id = await self.get_source_id(source_slug)
        events = list(
            await self.session.scalars(
                select(Event).where(Event.city_slug == city_slug, Event.source_id == source_id)
            )
        )
        for event in events:
            await self.session.delete(event)
        if events:
            await self.session.flush()
        return len(events)

    def _active_window_query(self, *, include_online: bool = False) -> Select[tuple[Event]]:
        now = datetime.now(tz=UTC)
        horizon = now + timedelta(days=30)
        clauses = [Event.start_at > now, Event.start_at <= horizon]
        if not include_online:
            clauses.append(Event.is_online.is_(False))
        return select(Event).where(and_(*clauses))

    @staticmethod
    def _event_source_slug(event: Event) -> str | None:
        source = getattr(event, "source", None)
        return getattr(source, "slug", None)

    @classmethod
    def _dedupe_for_display(cls, events: list[Event]) -> list[Event]:
        seen: set[tuple[str, str]] = set()
        unique: list[Event] = []
        for event in events:
            group_key = event.dedup_group_id or event.id
            source_slug = cls._event_source_slug(event) or "unknown"
            dedupe_key = (group_key, source_slug)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            unique.append(event)
        return unique

    @classmethod
    def _interleave_by_source(cls, events: list[Event], *, limit: int) -> list[Event]:
        """Round-robin across sources; cap per source so one site cannot dominate the list."""
        if not events or limit <= 0:
            return []

        by_source: dict[str, list[Event]] = {}
        for event in events:
            source_slug = cls._event_source_slug(event) or "unknown"
            by_source.setdefault(source_slug, []).append(event)

        num_sources = len(by_source)
        per_source_cap = max(1, (limit + num_sources - 1) // num_sources)
        min_pool = min(len(items) for items in by_source.values())
        per_source_cap = min(per_source_cap, max(min_pool * 2, 2))

        queues = {slug: list(items) for slug, items in by_source.items()}
        source_order = sorted(queues)
        picked: list[Event] = []
        picked_keys: set[tuple[str, str]] = set()
        source_counts: dict[str, int] = {slug: 0 for slug in source_order}
        last_source: str | None = None

        while len(picked) < limit:
            progress = False
            rotation = source_order
            if last_source is not None and num_sources > 1:
                rotation = [slug for slug in source_order if slug != last_source] + [last_source]
            for source_slug in rotation:
                if source_counts[source_slug] >= per_source_cap:
                    continue
                while queues[source_slug]:
                    candidate = queues[source_slug][0]
                    pick_key = (candidate.dedup_group_id or candidate.id, source_slug)
                    if pick_key in picked_keys:
                        queues[source_slug].pop(0)
                        continue
                    picked_keys.add(pick_key)
                    picked.append(queues[source_slug].pop(0))
                    source_counts[source_slug] += 1
                    last_source = source_slug
                    progress = True
                    break
                if len(picked) >= limit:
                    break
            if not progress:
                break
        return picked[:limit]

    _pick_popular_diverse = _interleave_by_source

    async def _source_ids_for_query(self, city_slug: str, base_clauses) -> list[str]:
        query = (
            select(Event.source_id)
            .where(and_(Event.city_slug == city_slug, *base_clauses))
            .where(self._publishable_events_filter())
            .distinct()
        )
        return list(await self.session.scalars(query))

    async def _fetch_balanced_events(
        self,
        *,
        city_slug: str,
        base_clauses,
        order_by,
        pool_limit: int,
        per_source_limit: int,
        options,
    ) -> list[Event]:
        source_ids = await self._source_ids_for_query(city_slug, base_clauses)
        if not source_ids:
            return []

        per_source = max(5, min(per_source_limit, pool_limit // max(len(source_ids), 1)))
        combined: list[Event] = []
        for source_id in source_ids:
            query = (
                select(Event)
                .where(and_(Event.city_slug == city_slug, Event.source_id == source_id, *base_clauses))
                .where(self._publishable_events_filter())
                .order_by(*order_by)
                .limit(per_source)
                .options(*options)
            )
            combined.extend(await self.session.scalars(query))
        return combined

    @staticmethod
    def _filter_events_by_date(events: list[Event], start: datetime, end: datetime) -> list[Event]:
        return [event for event in events if event_in_date_range(event, start, end)]

    async def _apply_list_filters(
        self,
        events: list[Event],
        city_slug: str,
        start: datetime | None,
        end: datetime | None,
    ) -> list[Event]:
        visibility = {"start": start, "end": end, "active_window": not (start and end)}
        hide_social = not await self.social_sources_enabled(city_slug, **visibility)
        social_ids = set(await self._social_source_ids()) if hide_social else set()
        filtered: list[Event] = []
        for event in events:
            if not is_publishable_event_url(event.source_url):
                continue
            if hide_social and event.source_id in social_ids:
                continue
            filtered.append(event)
        return filtered

    async def list_by_city_category(
        self,
        city_slug: str,
        category_slug: str,
        limit: int = 20,
        selected_date: date | None = None,
    ) -> list[Event]:
        category_id = await self.get_category_id(category_slug)
        start, end = self._date_range(selected_date)
        base_clauses = [Event.category_id == category_id]
        order_by = (Event.popularity_score.desc(), Event.start_at.asc())
        options = (joinedload(Event.category), joinedload(Event.source))

        if start and end:
            base_clauses.append(Event.start_at_confirmed.is_(True))
            events = await self._fetch_balanced_events(
                city_slug=city_slug,
                base_clauses=base_clauses,
                order_by=order_by,
                pool_limit=max(limit * 5, 100),
                per_source_limit=25,
                options=options,
            )
            events = self._filter_events_by_date(events, start, end)
        else:
            now = datetime.now(tz=UTC)
            horizon = now + timedelta(days=30)
            base_clauses.extend([Event.start_at > now, Event.start_at <= horizon, Event.is_online.is_(False)])
            events = await self._fetch_balanced_events(
                city_slug=city_slug,
                base_clauses=base_clauses,
                order_by=order_by,
                pool_limit=max(limit * 5, 100),
                per_source_limit=25,
                options=options,
            )

        events = await self._apply_list_filters(events, city_slug, start, end)
        unique = self._dedupe_for_display(events)
        return self._interleave_by_source(unique, limit=limit)

    async def list_candidates_for_ai(
        self,
        city_slug: str,
        limit: int = 100,
        selected_date: date | None = None,
    ) -> list[Event]:
        start, end = self._date_range(selected_date)
        if start and end:
            query = (
                select(Event)
                .where(
                    and_(
                        Event.city_slug == city_slug,
                        Event.start_at >= start,
                        Event.start_at < end,
                        Event.start_at_confirmed.is_(True),
                    )
                )
                .order_by(Event.popularity_score.desc(), Event.start_at.asc())
                .limit(limit)
                .options(joinedload(Event.category), joinedload(Event.source))
            )
        else:
            query = (
                self._active_window_query(include_online=True)
                .where(Event.city_slug == city_slug)
                .order_by(Event.start_at.asc())
                .limit(limit)
                .options(joinedload(Event.category), joinedload(Event.source))
            )
        visibility = {"start": start, "end": end, "active_window": not (start and end)}
        query = await self.apply_social_visibility(query, city_slug, **visibility)
        query = self._apply_publishable_filter(query)
        result = list(await self.session.scalars(query))
        return self._interleave_by_source(result, limit=limit)

    async def list_popular(
        self,
        city_slug: str,
        limit: int = 10,
        selected_date: date | None = None,
    ) -> list[Event]:
        start, end = self._date_range(selected_date)
        order_by = (Event.popularity_score.desc(), Event.start_at.asc())
        options = (joinedload(Event.category), joinedload(Event.source))

        if start and end:
            base_clauses = [Event.start_at_confirmed.is_(True)]
            events = await self._fetch_balanced_events(
                city_slug=city_slug,
                base_clauses=base_clauses,
                order_by=order_by,
                pool_limit=240,
                per_source_limit=40,
                options=options,
            )
            events = self._filter_events_by_date(events, start, end)
        else:
            now = datetime.now(tz=UTC)
            horizon = now + timedelta(days=30)
            base_clauses = [Event.start_at > now, Event.start_at <= horizon]
            events = await self._fetch_balanced_events(
                city_slug=city_slug,
                base_clauses=base_clauses,
                order_by=order_by,
                pool_limit=360,
                per_source_limit=50,
                options=options,
            )

        events = await self._apply_list_filters(events, city_slug, start, end)
        unique = self._dedupe_for_display(events)
        interleaved = self._interleave_by_source(unique, limit=max(limit * 2, 20))
        random.shuffle(interleaved)
        return interleaved[:limit]

    async def pick_random(
        self,
        city_slug: str,
        exclude_ids: list[str] | None = None,
        selected_date: date | None = None,
    ) -> Event | None:
        start, end = self._date_range(selected_date)
        order_by = (func.random(),)
        options = (joinedload(Event.category), joinedload(Event.source))

        if start and end:
            base_clauses = [Event.start_at_confirmed.is_(True)]
            events = await self._fetch_balanced_events(
                city_slug=city_slug,
                base_clauses=base_clauses,
                order_by=order_by,
                pool_limit=400,
                per_source_limit=50,
                options=options,
            )
            events = self._filter_events_by_date(events, start, end)
        else:
            now = datetime.now(tz=UTC)
            horizon = now + timedelta(days=30)
            base_clauses = [Event.start_at > now, Event.start_at <= horizon]
            events = await self._fetch_balanced_events(
                city_slug=city_slug,
                base_clauses=base_clauses,
                order_by=order_by,
                pool_limit=400,
                per_source_limit=50,
                options=options,
            )

        events = await self._apply_list_filters(events, city_slug, start, end)
        if exclude_ids:
            excluded = set(exclude_ids)
            events = [event for event in events if event.id not in excluded]
        if not events:
            return None
        return random.choice(events)

    async def get_by_id(self, event_id: str) -> Event | None:
        return await self.session.scalar(
            select(Event)
            .where(Event.id == event_id)
            .options(joinedload(Event.category), joinedload(Event.source))
        )

    async def get_by_ids(self, event_ids: list[str]) -> list[Event]:
        if not event_ids:
            return []
        query = select(Event).where(Event.id.in_(event_ids)).options(
            joinedload(Event.category), joinedload(Event.source)
        )
        result = await self.session.scalars(query)
        by_id = {item.id: item for item in result}
        return [by_id[event_id] for event_id in event_ids if event_id in by_id]

    async def list_unclassified(self, limit: int = 200) -> list[Event]:
        query = (
            select(Event)
            .where(Event.activity_slug.is_(None))
            .limit(limit)
            .options(joinedload(Event.category), joinedload(Event.source))
        )
        return list(await self.session.scalars(query))

    async def _find_dedup_target(self, dto: EventDTO) -> Event | None:
        same_city_query = self._active_window_query(include_online=True).where(Event.city_slug == dto.city_slug)
        events = list(await self.session.scalars(same_city_query))
        for existing in events:
            same_day = existing.start_at.date() == dto.start_at.date()
            title_score = fuzz.token_sort_ratio(existing.title, dto.title)
            if not same_day or title_score < 80:
                continue
            has_venue = bool((existing.venue or "").strip()) or bool((dto.venue or "").strip())
            if not has_venue:
                if title_score >= 95:
                    return existing
                continue
            venue_score = fuzz.token_sort_ratio(existing.venue or "", dto.venue or "")
            if venue_score >= 70:
                return existing
        return None

    async def upsert_event(self, dto: EventDTO, *, popularity_score: int | None = None) -> Event:
        if not is_publishable_event_url(str(dto.source_url)):
            raise ValueError(f"Refusing unpublishable event URL: {dto.source_url}")
        existing = await self.session.scalar(select(Event).where(Event.source_url == str(dto.source_url)))
        category_id = await self.get_category_id(dto.category_slug)
        source_id = await self.get_source_id(dto.source_slug)

        dedup_target = await self._find_dedup_target(dto)
        dedup_group_id = dedup_target.dedup_group_id if dedup_target else None
        if dedup_target and dedup_group_id is None:
            dedup_group_id = str(uuid.uuid4())
            dedup_target.dedup_group_id = dedup_group_id
            await self.session.flush()

        score = popularity_score if popularity_score is not None else dto.popularity_score
        session_starts_at = [item.astimezone(UTC).isoformat() for item in dto.session_starts_at]
        fields = dict(
            source_id=source_id,
            external_id=dto.external_id,
            title=dto.title,
            description=dto.description,
            category_id=category_id,
            activity_slug=dto.activity_slug,
            city_slug=dto.city_slug,
            venue=dto.venue,
            address=dto.address,
            start_at=dto.start_at,
            start_at_confirmed=dto.start_at_confirmed,
            session_starts_at=session_starts_at,
            end_at=dto.end_at,
            price_type=dto.price_type,
            price_text=dto.price_text,
            price_amount_rub=dto.price_amount_rub,
            venue_format=dto.venue_format,
            audience_tags=list(dto.audience_tags),
            popularity_score=score,
            is_online=dto.is_online,
            image_url=str(dto.image_url) if dto.image_url else None,
            synced_at=datetime.now(tz=UTC),
        )

        if existing is None:
            existing = Event(
                source_url=str(dto.source_url),
                dedup_group_id=dedup_group_id,
                **fields,
            )
            self.session.add(existing)
        else:
            for key, value in fields.items():
                setattr(existing, key, value)
            if dedup_group_id:
                existing.dedup_group_id = dedup_group_id

        await self.session.flush()
        return existing
