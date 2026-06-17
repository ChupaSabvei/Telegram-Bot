from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.bot.handlers.categories import router as categories_router
from src.bot.handlers.date_filter import router as date_filter_router
from src.bot.handlers.event_detail import router as event_detail_router
from src.bot.handlers.collections import router as collections_router
from src.bot.handlers.favorites import router as favorites_router
from src.bot.handlers.messages import router as messages_router
from src.bot.handlers.navigation import router as navigation_router
from src.bot.handlers.popular import router as popular_router
from src.bot.handlers.random import router as random_router
from src.bot.handlers.settings import router as settings_router
from src.bot.handlers.start import router as start_router
from src.bot.handlers.survey import router as survey_router
from src.bot.proxy import resolve_telegram_proxy
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


def create_bot(cfg) -> Bot:  # type: ignore[no-untyped-def]
    proxy = resolve_telegram_proxy(cfg.telegram_proxy)
    if proxy:
        logging.info("Telegram proxy enabled: %s", proxy)
        session = AiohttpSession(proxy=proxy)
        return Bot(token=cfg.bot_token, session=session)
    return Bot(token=cfg.bot_token)


async def run_bot() -> None:
    cfg = get_config()
    await bootstrap()

    bot = create_bot(cfg)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(survey_router)
    dp.include_router(date_filter_router)
    dp.include_router(navigation_router)
    dp.include_router(random_router)
    dp.include_router(popular_router)
    dp.include_router(favorites_router)
    dp.include_router(collections_router)
    dp.include_router(categories_router)
    dp.include_router(event_detail_router)
    dp.include_router(messages_router)

    @dp.message(~F.text)
    async def reject_non_text(message):  # type: ignore[no-untyped-def]
        await message.answer("Пожалуйста, опишите запрос текстом или выберите кнопку меню.")

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
