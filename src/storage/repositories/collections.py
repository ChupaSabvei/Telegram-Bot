from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.storage.models import CollectionItem, Event, EventCollection

MAX_COLLECTIONS_PER_USER = 20
MAX_ITEMS_PER_COLLECTION = 10


def _generate_share_token() -> str:
    return secrets.token_urlsafe(9)[:12]


class CollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_for_owner(self, telegram_id: int) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(EventCollection)
                .where(EventCollection.owner_telegram_id == telegram_id)
            )
            or 0
        )

    async def create(self, telegram_id: int, title: str) -> EventCollection:
        if await self.count_for_owner(telegram_id) >= MAX_COLLECTIONS_PER_USER:
            raise ValueError("collection_limit_reached")
        for _ in range(5):
            token = _generate_share_token()
            exists = await self.session.scalar(
                select(EventCollection.id).where(EventCollection.share_token == token)
            )
            if exists is None:
                break
        else:
            raise RuntimeError("Failed to generate unique share token")

        collection = EventCollection(
            owner_telegram_id=telegram_id,
            title=title.strip()[:120],
            share_token=token,
        )
        self.session.add(collection)
        await self.session.flush()
        return collection

    async def get_owned(self, collection_id: str, telegram_id: int) -> EventCollection | None:
        return await self.session.scalar(
            select(EventCollection).where(
                EventCollection.id == collection_id,
                EventCollection.owner_telegram_id == telegram_id,
            )
        )

    async def get_by_share_token(self, share_token: str) -> EventCollection | None:
        return await self.session.scalar(
            select(EventCollection)
            .where(EventCollection.share_token == share_token)
            .options(selectinload(EventCollection.items).joinedload(CollectionItem.event))
        )

    async def list_for_owner(self, telegram_id: int) -> list[EventCollection]:
        result = await self.session.scalars(
            select(EventCollection)
            .where(EventCollection.owner_telegram_id == telegram_id)
            .order_by(EventCollection.updated_at.desc())
            .options(selectinload(EventCollection.items))
        )
        return list(result)

    async def list_events(self, collection_id: str) -> list[Event]:
        result = await self.session.scalars(
            select(Event)
            .join(CollectionItem, CollectionItem.event_id == Event.id)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.sort_order.asc(), CollectionItem.added_at.asc())
            .options(joinedload(Event.category), joinedload(Event.source))
        )
        return list(result)

    async def add_events(self, collection_id: str, event_ids: list[str]) -> int:
        if not event_ids:
            return 0
        existing_ids = set(
            await self.session.scalars(
                select(CollectionItem.event_id).where(CollectionItem.collection_id == collection_id)
            )
        )
        current_count = len(existing_ids)
        max_sort = await self.session.scalar(
            select(func.max(CollectionItem.sort_order)).where(
                CollectionItem.collection_id == collection_id
            )
        )
        next_sort = (max_sort or 0) + 1
        added = 0
        for event_id in event_ids:
            if event_id in existing_ids:
                continue
            if current_count + added >= MAX_ITEMS_PER_COLLECTION:
                break
            self.session.add(
                CollectionItem(
                    collection_id=collection_id,
                    event_id=event_id,
                    sort_order=next_sort,
                )
            )
            next_sort += 1
            added += 1

        if added:
            collection = await self.session.get(EventCollection, collection_id)
            if collection is not None:
                collection.updated_at = datetime.now(tz=UTC)
            await self.session.flush()
        return added

    async def rename(self, collection_id: str, telegram_id: int, title: str) -> bool:
        collection = await self.get_owned(collection_id, telegram_id)
        if collection is None:
            return False
        cleaned = title.strip()[:120]
        if not cleaned:
            return False
        collection.title = cleaned
        collection.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        return True

    async def remove_event(self, collection_id: str, telegram_id: int, event_id: str) -> bool:
        collection = await self.get_owned(collection_id, telegram_id)
        if collection is None:
            return False
        item = await self.session.scalar(
            select(CollectionItem).where(
                CollectionItem.collection_id == collection_id,
                CollectionItem.event_id == event_id,
            )
        )
        if item is None:
            return False
        await self.session.delete(item)
        collection.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        return True

    async def delete(self, collection_id: str, telegram_id: int) -> bool:
        collection = await self.get_owned(collection_id, telegram_id)
        if collection is None:
            return False
        await self.session.delete(collection)
        await self.session.flush()
        return True
