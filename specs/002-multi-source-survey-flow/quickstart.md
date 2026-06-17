# Quickstart: Мульти-источники и опросный подбор

**Branch**: `002-multi-source-survey-flow` | **Date**: 2026-06-14

End-to-end validation for feature 002. See [data-model.md](./data-model.md) and [contracts/](./contracts/).

## Prerequisites

- Python 3.11+
- Completed setup from [001 quickstart](../001-ai-event-discovery/quickstart.md)
- Branch `002-multi-source-survey-flow`
- `BOT_TOKEN`, `OPENAI_API_KEY` (or Groq-compatible), `DATABASE_URL` in `.env`

## Setup

```bash
git checkout 002-multi-source-survey-flow
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Apply 002 migrations
python -m src.storage.database migrate

# Seed new event sources
python -m src.storage.database seed
```

## Sync Moscow (all sources)

```bash
python scripts/sync_events.py --city moscow --verbose
```

**Expected** (SC-002):

- Log lines for ≥ 5 distinct `source_slug` with `saved > 0`
- Total unique Moscow events in 30-day window ≥ 200:

```bash
python scripts/count_events.py --city moscow --days 30
```

## Run Bot

```bash
python -m src.bot.main
```

## Validation Scenarios

### V1 — City → Main Menu (FR-001, FR-002)

1. New user: `/start`
2. Select «Москва»
3. **Expected**: 4 buttons — 🎲 / 📝 / 🔥 / ❤️ (not survey yet)

### V2 — Full Survey Flow (US1, SC-001)

1. Tap «📝 Опрос»
2. Семья → Семейный отдых → до 3000₽ → Всё равно
3. **Expected** within 5 s: card with header «Для семьи…», price, format, navigator link
4. **Expected** buttons: Другой вариант | В избранное | Заново

### V3 — Another Variant (FR-006, SC-004)

1. From V2 card, tap «➡️ Другой вариант» twice
2. **Expected**: different titles when ≥ 2 matches exist; no duplicate in session

### V4 — Empty Filters (FR-020)

1. Complete survey with narrow combo (e.g. У дома + Бесплатно + Гастро) if empty
2. **Expected**: «ничего не найдено» + 3 recovery buttons (no auto-relaxed results)

### V5 — Random (US3)

1. Main menu → «🎲 Случайный вариант»
2. **Expected**: one card < 5 s; «Заново» → main menu

### V6 — Popular (US4, FR-013)

1. «🔥 Популярное»
2. **Expected**: 5 numbered items + «Показать ещё»
3. Tap «Показать ещё» → up to 10 items
4. Open item → full card

### V7 — Favorites (US5, FR-014)

1. Save card via «❤️ В избранное»
2. Main menu → «❤️ Избранное»
3. **Expected**: saved event listed
4. Restart bot process; open favorites again → still present

### V8 — Free Text AI (US1b, FR-018)

1. Main menu: send «бильярд рядом»
2. **Expected**: AI/places response (not survey step)
3. Start survey, on step 2 send «концерты» text
4. **Expected**: survey reset; AI answers about concerts

### V9 — Multi-Source Data (US2)

```bash
rtk pytest tests/unit/scrapers/ -q
rtk pytest tests/integration/test_moscow_sync.py -q
```

**Expected**: all scraper fixture tests pass; Moscow integration reports ≥ 5 sources

## Automated Tests

```bash
rtk pytest tests/ -q
rtk ruff check src tests
```

**Expected**: green CI; new tests for survey FSM, matcher, favorites, formatters

## Rollback

If sync breaks DB:

```bash
git checkout 001-ai-event-discovery -- src/scrapers/
python -m src.storage.database migrate downgrade
```
