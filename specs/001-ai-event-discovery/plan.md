# Implementation Plan: ИИ-помощник для подбора мероприятий

**Branch**: `001-ai-event-discovery` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-ai-event-discovery/spec.md`

## Summary

Telegram-бот с ИИ-помощником для подбора **очных** мероприятий по категориям
в выбранном городе России. Данные собираются с агрегаторов афиш (обязательно
Яндекс Афиша + второй агрегатор), нормализуются в единую схему, хранятся в БД
и отдаются пользователю через inline-клавиатуру и текстовый ИИ-поиск.

Технический подход: Python 3.11, **aiogram 3** (async), модульная архитектура
(`bot` / `scrapers` / `ai` / `storage`), **SQLite** локально и **PostgreSQL**
(Supabase) в проде, ежедневная фоновая синхронизация, **OpenAI-compatible API**
для ранжирования и интерпретации запросов.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: aiogram 3.x, httpx, BeautifulSoup4, pydantic v2,
SQLAlchemy 2.x (async), APScheduler, openai (SDK), python-dotenv

**Storage**: SQLite (локальная разработка); PostgreSQL / Supabase (продакшен и
командная среда)

**Testing**: pytest, pytest-asyncio, pytest-cov; фикстуры HTML для скраперов;
contract-тесты по `contracts/`

**Target Platform**: Linux VPS или PaaS (Railway, Fly.io, VPS); разработка на
Windows/macOS/Linux

**Project Type**: single-project Telegram bot + background scraper jobs

**Performance Goals**: ответ бота p95 < 10 с (SC-001); синхронизация источников
не блокирует event loop бота

**Constraints**: горизонт 30 дней; только офлайн; секреты в `.env`; скраперы
уважают rate limits; без Playwright в MVP (если парсинг невозможен — эскалация
в tasks)

**Scale/Scope**: MVP — 10+ городов-миллионников, 2 агрегатора, 50+ событий,
4 user stories, ~15 Telegram-экранов/состояний

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md` (v1.0.0)

- [x] **Modular Architecture**: код в `src/bot/`, `src/scrapers/`, `src/ai/`,
      `src/storage/`; контракты в `contracts/event-schema.json` и
      `contracts/scraper-interface.md`
- [x] **AI-Assisted Discovery**: `src/ai/ranker.py` + fallback на категории
      (см. `contracts/ai-assistant-contract.md`)
- [x] **Data Ingestion**: плагинные скраперы → `Event` schema; ошибки изолированы
      в job runner
- [x] **Test-First**: contract + unit + integration тесты запланированы в
      `quickstart.md` и `tasks.md` (следующий этап)
- [x] **GitHub Workflow**: ветка `001-ai-event-discovery`, PR, CI (pytest + ruff)
- [x] **Security**: `.env.example` с `BOT_TOKEN`, `OPENAI_API_KEY`, `DATABASE_URL`

*Post-design re-check (Phase 1): все gates пройдены, нарушений конституции нет.*

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-event-discovery/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── event-schema.json
│   ├── scraper-interface.md
│   ├── ai-assistant-contract.md
│   └── bot-commands.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point, dispatcher
│   ├── handlers/
│   │   ├── start.py         # /start, city onboarding
│   │   ├── categories.py    # Category browse
│   │   ├── search.py        # AI text search
│   │   ├── event_detail.py  # Event card
│   │   └── settings.py      # City change
│   ├── keyboards/           # Inline/reply keyboards
│   └── formatters/          # Message templates
├── scrapers/
│   ├── __init__.py
│   ├── base.py              # ScraperProtocol
│   ├── runner.py            # Sync job orchestration
│   ├── yandex_afisha.py
│   └── kudago.py
├── ai/
│   ├── __init__.py
│   ├── client.py            # LLM client wrapper
│   ├── prompts.py           # Versioned prompts
│   └── ranker.py            # Query → ranked event IDs
└── storage/
    ├── __init__.py
    ├── models.py            # SQLAlchemy models
    ├── schemas.py           # Pydantic DTOs (Event, UserSettings)
    ├── repositories/
    │   ├── events.py
    │   └── users.py
    └── database.py          # Engine/session factory

tests/
├── contract/
│   ├── test_event_schema.py
│   └── test_scraper_output.py
├── integration/
│   ├── test_bot_onboarding.py
│   └── test_scraper_sync.py
└── unit/
    ├── test_dedup.py
    ├── test_ai_ranker.py
    └── test_filters.py

scripts/
└── sync_events.py           # Manual/CI scraper run

.github/
└── workflows/
    └── ci.yml                 # ruff + pytest

.env.example
requirements.txt
pyproject.toml                 # ruff config
```

**Structure Decision**: Single-project layout per constitution. Скраперы и бот
делят `storage` через репозитории; ИИ-модуль не импортирует Telegram SDK.
Фоновая синхронизация — отдельная asyncio-задача в `main.py` + CLI
`scripts/sync_events.py` для отладки.

## Complexity Tracking

> Нарушений конституции нет. Таблица пуста намеренно.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
