from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.bot.handlers.categories import router as categories_router
from src.bot.handlers.event_detail import router as event_detail_router
from src.bot.handlers.search import router as search_router
from src.bot.handlers.settings import router as settings_router
from src.bot.handlers.start import router as start_router
from src.config import get_config
from src.scrapers.runner import sync_all_sources
from src.storage.database import build_runtime, init_db, seed_defaults


async def sync_job() -> None:
    report = await sync_all_sources()
    logging.info("Daily sync complete, saved=%s", report.total_saved)


async def bootstrap() -> None:
    runtime = build_runtime()
    await init_db(runtime)
    await seed_defaults(runtime)


async def run_bot() -> None:
    cfg = get_config()
    await bootstrap()

    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(categories_router)
    dp.include_router(event_detail_router)
    dp.include_router(search_router)

    @dp.message(~F.text)
    async def reject_non_text(message):  # type: ignore[no-untyped-def]
        await message.answer("Пожалуйста, опишите запрос текстом или выберите категорию.")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_job, trigger="cron", hour=3, minute=0)
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
