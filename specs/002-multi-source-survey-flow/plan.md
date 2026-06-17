# Implementation Plan: Мульти-источники и опросный подбор

**Branch**: `002-multi-source-survey-flow` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-multi-source-survey-flow/spec.md`

## Summary

Расширение Telegram Event Bot: **8+ источников афиш** (Moscow-first) и новый **опросный UX** — город → главное меню (4 основные кнопки + ⚙️ Настройки) → опрос из 4 шагов → персонализированная карточка. Дополнительно: случайный вариант, популярное (5+«ещё»), избранное, **ИИ на свободный текст** и **ИИ-классификация `activity_slug` при sync** (FR-021/023).

Технический подход: расширить `EventDTO`/БД (activity_slug, venue_format, popularity_score, favorites), добавить scrapers по plugin-паттерну, pipeline ingest **rule-based → AI → unclassified retry**, rule-based `survey_matcher` (без LLM в опросе), aiogram FSM `SurveyStates`, единый `survey_card` formatter. ИИ: free text (001 pipeline) + `activity_classifier` при sync. Без Playwright в первой волне; SPA-источники — httpx + embedded JSON, Playwright как escape hatch в tasks.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: aiogram 3.x, httpx, BeautifulSoup4, pydantic v2, SQLAlchemy 2.x (async), APScheduler, openai SDK, python-dotenv, rapidfuzz

**Storage**: SQLite (dev) / PostgreSQL Supabase (prod); новая таблица `favorites`; миграция колонок `events`

**Testing**: pytest, pytest-asyncio; fixtures HTML per scraper; FSM integration tests; survey_matcher unit tests

**Target Platform**: Linux VPS / PaaS; dev Windows/macOS/Linux

**Project Type**: single-project Telegram bot + background sync jobs

**Performance Goals**: callback p95 < 5 s (FR-016); Moscow sync ≥ 200 events / 30 d from ≥ 5 sources (SC-002)

**Constraints**: Moscow-first new scrapers; secrets in `.env`; rate limits; AI optional for survey; Yandex Afisha best-effort

**Scale/Scope**: 7 new scrapers (Moscow), 4 new bot flows, ~12 FSM states, favorites CRUD, extend Event schema

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md` (v1.0.0)

- [x] **Modular Architecture**: scrapers → `src/scrapers/`; bot FSM → `src/bot/`; matcher → `src/bot/services/`; favorites → `src/storage/`
- [x] **AI-Assisted Discovery**: free text → existing `src/ai/`; survey = rules (FR-022); ingest `activity_slug` → rule-based + AI fallback (FR-021/023); graceful AI degradation (FR-015)
- [x] **Data Ingestion**: plugin scrapers, EventDTO v2, per-source sync status, dedup preserved
- [x] **Test-First**: contract tests + unit scraper fixtures + FSM/matcher tests in quickstart
- [x] **GitHub Workflow**: branch `002-multi-source-survey-flow`, PR, CI pytest + ruff
- [x] **Security**: no new secrets required; scraper User-Agent documented

*Post-design re-check (Phase 1): all gates pass. No constitution violations.*

## Project Structure

### Documentation (this feature)

```text
specs/002-multi-source-survey-flow/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── event-schema-v2.json
│   ├── bot-survey-flow.md
│   ├── scraper-sources.md
│   └── survey-matcher-contract.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (additions / changes)

```text
src/
├── bot/
│   ├── handlers/
│   │   ├── start.py           # Main menu 4 + settings
│   │   ├── survey.py          # NEW: survey FSM steps
│   │   ├── random.py          # NEW: random card
│   │   ├── popular.py         # NEW: popular list
│   │   ├── favorites.py       # NEW: favorites list
│   │   ├── messages.py        # NEW: free text router → AI
│   │   ├── search.py          # Existing AI (reuse)
│   │   └── categories.py      # Deprecated entry, kept
│   ├── keyboards/
│   │   ├── main_menu.py       # NEW
│   │   └── survey.py          # NEW
│   ├── formatters/
│   │   └── survey_card.py     # NEW unified card
│   ├── services/
│   │   └── survey_matcher.py  # NEW
│   └── states.py              # + SurveyStates, PopularStates
├── scrapers/
│   ├── timepad.py             # NEW
│   ├── mts_live.py            # NEW
│   ├── tbank_gorod.py         # NEW
│   ├── mos_kultura.py         # NEW
│   ├── timeout_msk.py         # NEW
│   ├── mos_sport_rayon.py     # NEW
│   ├── mtpp.py                # NEW
│   ├── classifiers/
│   │   └── activity.py        # NEW
│   └── runner.py              # Register new scrapers
├── ai/
│   └── activity_classifier.py # NEW: activity_slug at sync (FR-021)
└── storage/
    ├── models.py              # Favorite, Event columns
    ├── schemas.py             # EventDTO v2, enums
    └── repositories/
        ├── favorites.py       # NEW
        └── events.py          # survey/popular queries

tests/
├── unit/
│   ├── scrapers/              # Per-source fixture tests
│   ├── test_survey_matcher.py
│   ├── test_survey_card.py
│   └── test_activity_classifier.py
├── integration/
│   ├── test_survey_fsm.py
│   └── test_moscow_sync.py
└── fixtures/html/             # New source HTML samples
```

**Structure Decision**: Single-project layout per constitution; new handlers split by flow (survey/random/popular/favorites) to keep files < 300 LOC.

## Complexity Tracking

No constitution violations requiring justification.

## Implementation Phases (for /speckit-tasks)

### Phase A — Foundation (P1)

1. DB migration: `activity_slug`, `venue_format`, `price_amount_rub`, `audience_tags`, `address`; `favorites` table
2. Extend `EventDTO`, `event-schema-v2.json` validation in tests
3. `SurveyStates`, main menu keyboards, `/start` → city → 4 main buttons + ⚙️ Настройки
4. `activity_classifier` + rule-based classifier; runner pipeline rule → AI → unclassified (FR-021/023)
5. `survey_matcher` + repository query methods
6. `handlers/survey.py` full 4-step flow + result card + empty state
7. Unit tests for matcher, formatters, activity classifier

### Phase B — Discovery Modes (P2)

7. `handlers/random.py`, `handlers/popular.py` (5 + more)
8. `handlers/favorites.py` + repository
9. `handlers/messages.py` free text → AI; survey text → reset + AI
10. Integration tests V1–V8 from quickstart

### Phase C — Scrapers Moscow (P1)

11. P1 scrapers: timepad, mts_live, mos_sport_rayon + fixtures + tests
12. P2 scrapers: tbank_gorod, timeout_msk, mos_kultura
13. P3: mtpp
14. Rule-based + AI classifiers; runner registration; seed sources
15. Integration test SC-002 gate (≥ 200 events, ≥ 5 sources)

### Phase D — Polish

16. Deprecate category buttons from main menu (keep `/categories`)
17. README update; popularity_score computation
18. Manual quickstart walkthrough

## Risk Register

| Risk | Mitigation |
|------|------------|
| T-Bank / MTS SPA without static HTML | Research JSON endpoints; defer Playwright to stretch task |
| Yandex Afisha 403 | Non-blocking; other sources satisfy SC-002 |
| Low activity_slug coverage on old events | Runner re-classifies on sync; one-time backfill script for legacy rows; unclassified excluded from survey until classified |
| Telegram callback 64-byte limit | Short prefixes (`survey:act:sport`) |

## Artifacts Generated

| Artifact | Path | Status |
|----------|------|--------|
| Research | [research.md](./research.md) | ✅ |
| Data model | [data-model.md](./data-model.md) | ✅ |
| Event schema v2 | [contracts/event-schema-v2.json](./contracts/event-schema-v2.json) | ✅ |
| Bot survey flow | [contracts/bot-survey-flow.md](./contracts/bot-survey-flow.md) | ✅ |
| Scraper sources | [contracts/scraper-sources.md](./contracts/scraper-sources.md) | ✅ |
| Survey matcher | [contracts/survey-matcher-contract.md](./contracts/survey-matcher-contract.md) | ✅ |
| Quickstart | [quickstart.md](./quickstart.md) | ✅ |
| Tasks | [tasks.md](./tasks.md) | ✅ |

## Next Step

Run **`/speckit-implement`** (Phase 1–2 foundation, then US1/US1b MVP).
