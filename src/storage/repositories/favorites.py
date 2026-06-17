from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.storage.models import Event, Favorite


class FavoritesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, telegram_id: int, event_id: str) -> Favorite:
        existing = await self.session.scalar(
            select(Favorite).where(
                Favorite.telegram_id == telegram_id,
                Favorite.event_id == event_id,
            )
        )
        if existing:
            return existing
        fav = Favorite(telegram_id=telegram_id, event_id=event_id, saved_at=datetime.now(tz=UTC))
        self.session.add(fav)
        await self.session.flush()
        return fav

    async def list_for_user(self, telegram_id: int) -> list[Event]:
        query = (
            select(Event)
            .join(Favorite, Favorite.event_id == Event.id)
            .where(Favorite.telegram_id == telegram_id)
            .order_by(Favorite.saved_at.desc())
            .options(joinedload(Event.category), joinedload(Event.source))
        )
        return list(await self.session.scalars(query))

    async def is_saved(self, telegram_id: int, event_id: str) -> bool:
        row = await self.session.scalar(
            select(Favorite.id).where(
                Favorite.telegram_id == telegram_id,
                Favorite.event_id == event_id,
            )
        )
        return row is not None

    async def clear_for_user(self, telegram_id: int) -> int:
        result = await self.session.execute(delete(Favorite).where(Favorite.telegram_id == telegram_id))
        return int(result.rowcount or 0)
