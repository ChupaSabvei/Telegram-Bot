from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import UserSettings


class UserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, telegram_id: int) -> UserSettings | None:
        return await self.session.get(UserSettings, telegram_id)

    async def upsert_city(self, telegram_id: int, city_slug: str) -> UserSettings:
        existing = await self.get(telegram_id)
        if existing is None:
            existing = UserSettings(
                telegram_id=telegram_id,
                city_slug=city_slug,
                onboarding_complete=True,
                updated_at=datetime.now(tz=UTC),
            )
            self.session.add(existing)
        else:
            existing.city_slug = city_slug
            existing.onboarding_complete = True
            existing.updated_at = datetime.now(tz=UTC)
        await self.session.flush()
        return existing

    async def list_completed(self) -> list[UserSettings]:
        result = await self.session.scalars(
            select(UserSettings).where(UserSettings.onboarding_complete.is_(True))
        )
        return list(result)
