# Quickstart: ИИ-помощник для подбора мероприятий

**Branch**: `001-ai-event-discovery` | **Date**: 2026-06-12

Пошаговая проверка MVP end-to-end. Детали схем — в [data-model.md](./data-model.md),
контракты — в [contracts/](./contracts/).

## Prerequisites

- Python 3.11+
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- OpenAI API key (или совместимый endpoint)
- Git + ветка `001-ai-event-discovery`

## Setup

```bash
# Clone and checkout
git checkout 001-ai-event-discovery

# Virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt

# Environment
cp .env.example .env
# Заполнить: BOT_TOKEN, OPENAI_API_KEY, DATABASE_URL
# DATABASE_URL примеры:
#   sqlite+aiosqlite:///./data/bot.db
#   postgresql+asyncpg://user:pass@host:5432/events
```

## Initialize Database

```bash
python -m src.storage.database init
python -m src.storage.database seed   # categories + event sources
```

## Sync Events (scrapers)

```bash
# Одна синхронизация для Москвы (отладка)
python scripts/sync_events.py --city moscow

# Все города MVP
python scripts/sync_events.py --all-cities
```

**Expected**: в логе `saved >= 1` для kudago и/или yandex_afisha; в БД ≥ 50
событий для moscow+spb суммарно (SC-004).

## Run Bot

```bash
python -m src.bot.main
```

## Validation Scenarios

### V1 — Onboarding (US1, FR-003)

1. Отправить `/start` новому пользователю (чистый telegram_id)
2. **Expected**: приветствие + inline-клавиатура с городами
3. Нажать «Москва»
4. **Expected**: главное меню с 6 категориями

### V2 — Category Browse (US1, SC-001)

1. Нажать «Концерты»
2. **Expected**: список ≤ 10 событий с датой и местом; ответ < 10 с
3. Нажать на событие
4. **Expected**: карточка со стоимостью и ссылкой (US3)

### V3 — AI Search (US2, SC-002)

1. Написать: «джазовый концерт в эти выходные»
2. **Expected**: typing indicator → список релевантных событий
3. Повторить с «что-нибудь интересное»
4. **Expected**: уточняющий вопрос (clarification)

### V4 — AI Fallback (US2, SC-005)

1. В `.env` указать невалидный `OPENAI_API_KEY`
2. Перезапустить бота
3. Написать текстовый запрос
4. **Expected**: fallback-результаты или предложение выбрать категорию (не crash)

### V5 — Settings (US4)

1. `/settings` → выбрать «Санкт-Петербург»
2. **Expected**: подтверждение смены города
3. «Концерты»
4. **Expected**: события только для СПб

### V6 — Edge: Empty Category

1. Выбрать категорию без событий (если есть в тестовых данных)
2. **Expected**: сообщение «мероприятий не найдено» + предложение другой категории

## Automated Tests

```bash
# Unit + contract (no network)
pytest tests/unit tests/contract -v

# Integration (requires DB, mocked Telegram)
pytest tests/integration -v

# Lint
ruff check src tests
```

**CI equivalent**: `.github/workflows/ci.yml` runs the same on PR.

## Troubleshooting

| Problem | Check |
|---------|-------|
| 0 events after sync | `python scripts/sync_events.py --city moscow -v`; fixtures in tests |
| Bot not responding | `BOT_TOKEN` valid; polling mode; no second instance |
| AI timeout | Reduce candidates; check `OPENAI_API_KEY`; see fallback logs |
| Duplicate events in list | `dedup_group_id` logic in `tests/unit/test_dedup.py` |

## Next Step

После прохождения quickstart → `/speckit-tasks` для генерации `tasks.md`.
