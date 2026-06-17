from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_config
from src.storage.models import Base, Category, EventSource


@dataclass(slots=True)
class DatabaseRuntime:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def build_runtime(database_url: str | None = None) -> DatabaseRuntime:
    if database_url is None:
        cfg = get_config()
        database_url = cfg.database_url
    engine = create_async_engine(database_url, future=True)
    return DatabaseRuntime(engine=engine, session_factory=async_sessionmaker(engine, expire_on_commit=False))


DEFAULT_CATEGORIES = [
    ("concerts", "Концерты", "Живая музыка и выступления", 1),
    ("exhibitions", "Выставки", "Музеи, галереи и экспозиции", 2),
    ("theater", "Театр", "Спектакли и постановки", 3),
    ("sport", "Спорт", "Матчи и спортивные события", 4),
    ("education", "Образование", "Лекции и мастер-классы", 5),
    ("other", "Другое", "Прочие мероприятия", 6),
]

DEFAULT_SOURCES = [
    ("yandex_afisha", "Яндекс Афиша", "https://afisha.yandex.ru"),
    ("kudago", "KudaGo", "https://kudago.com"),
    ("timepad", "Timepad Afisha", "https://afisha.timepad.ru"),
    ("mts_live", "MTS Live", "https://live.mts.ru"),
    ("tbank_gorod", "T-Bank Город", "https://www.tbank.ru/gorod/afisha/"),
    ("mos_kultura", "Культура Москвы", "https://www.mos.ru/kultura/"),
    ("timeout_msk", "Time Out Москва", "https://www.timeout.ru/msk"),
    ("mos_sport_rayon", "Мой спортивный район", "https://moysportrayon.sport.mos.ru"),
    ("mtpp", "МТПП Календарь", "https://mostpp.ru"),
    ("telegram_channels", "Telegram каналы Москвы", "https://t.me"),
]

MIGRATION_002_STATEMENTS = [
    "ALTER TABLE events ADD COLUMN activity_slug VARCHAR(32)",
    "ALTER TABLE events ADD COLUMN venue_format VARCHAR(16) DEFAULT 'unknown'",
    "ALTER TABLE events ADD COLUMN price_amount_rub INTEGER",
    "ALTER TABLE events ADD COLUMN audience_tags JSON",
    "ALTER TABLE events ADD COLUMN address VARCHAR(500)",
    "ALTER TABLE events ADD COLUMN popularity_score INTEGER DEFAULT 0",
    "ALTER TABLE events ADD COLUMN start_at_confirmed BOOLEAN DEFAULT 1",
    "ALTER TABLE user_settings ADD COLUMN selected_date DATE",
    "ALTER TABLE events ADD COLUMN session_starts_at JSON",
]


async def apply_migration_002(runtime: DatabaseRuntime) -> None:
    """Best-effort SQLite/Postgres column adds for existing databases."""
    async with runtime.engine.begin() as conn:
        for statement in MIGRATION_002_STATEMENTS:
            try:
                await conn.exec_driver_sql(statement)
            except Exception:
                pass
        await conn.run_sync(Base.metadata.create_all)


async def init_db(runtime: DatabaseRuntime) -> None:
    async with runtime.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_migration_002(runtime)


async def seed_defaults(runtime: DatabaseRuntime) -> None:
    async with runtime.session_factory() as session:
        for slug, name_ru, description_ru, order in DEFAULT_CATEGORIES:
            exists = await session.scalar(select(Category).where(Category.slug == slug))
            if exists is None:
                session.add(
                    Category(slug=slug, name_ru=name_ru, description_ru=description_ru, sort_order=order)
                )

        for slug, name, base_url in DEFAULT_SOURCES:
            exists = await session.scalar(select(EventSource).where(EventSource.slug == slug))
            if exists is None:
                session.add(EventSource(slug=slug, name=name, base_url=base_url))

        await session.commit()


async def _cli_main(command: str) -> None:
    runtime = build_runtime()
    if command == "init":
        await init_db(runtime)
        return
    if command == "seed":
        await seed_defaults(runtime)
        return
    raise ValueError(f"Unsupported command: {command}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Database helpers")
    parser.add_argument("command", choices=["init", "seed"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(_cli_main(args.command))


if __name__ == "__main__":
    main()
