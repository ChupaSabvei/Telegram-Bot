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
]


async def init_db(runtime: DatabaseRuntime) -> None:
    async with runtime.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
