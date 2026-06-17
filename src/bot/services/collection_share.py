from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot


async def build_collection_share_link(bot: Bot, share_token: str) -> str:
    me = await bot.get_me()
    username = me.username or "bot"
    return f"https://t.me/{username}?start=share_{share_token}"


def default_collection_title(*, now: datetime | None = None) -> str:
    now = now or datetime.now(tz=UTC)
    return f"Подборка {now.astimezone(UTC).strftime('%d.%m')}"
