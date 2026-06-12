---
description: "Task list for ИИ-помощник для подбора мероприятий"
---

# Tasks: ИИ-помощник для подбора мероприятий

**Input**: Design documents from `specs/001-ai-event-discovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Включены — конституция v1.0.0 требует TDD для критических путей (скраперы,
схемы, ИИ-ранжирование, хендлеры бота).

**Organization**: Задачи сгруппированы по user story для независимой реализации и тестирования.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Можно выполнять параллельно (разные файлы, нет зависимостей от незавершённых задач)
- **[Story]**: US1–US4 — user story из spec.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Инициализация проекта и инструментов

- [ ] T001 Create `src/` module tree per plan.md (`bot/`, `scrapers/`, `ai/`, `storage/`)
- [ ] T002 [P] Create `requirements.txt` with aiogram, httpx, bs4, pydantic, sqlalchemy, apscheduler, openai, python-dotenv, rapidfuzz, pytest deps in `requirements.txt`
- [ ] T003 [P] Configure ruff in `pyproject.toml`
- [ ] T004 [P] Create `.env.example` with `BOT_TOKEN`, `OPENAI_API_KEY`, `DATABASE_URL` in `.env.example`
- [ ] T005 [P] Create GitHub Actions CI workflow in `.github/workflows/ci.yml` (ruff + pytest)
- [ ] T006 [P] Create `tests/` tree (`unit/`, `integration/`, `contract/`, `fixtures/`) with `conftest.py` in `tests/conftest.py`
- [ ] T007 Create CLI stub in `scripts/sync_events.py` with argparse (`--city`, `--all-cities`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: БД, скраперы, контракты — MUST завершить до любой user story

**⚠️ CRITICAL**: User story work cannot begin until this phase is complete

### Tests First (TDD — must FAIL before implementation)

- [ ] T008 [P] Contract test for `EventDTO` vs `specs/001-ai-event-discovery/contracts/event-schema.json` in `tests/contract/test_event_schema.py`
- [ ] T009 [P] Contract test for scraper output using HTML/API fixtures in `tests/contract/test_scraper_output.py`
- [ ] T010 [P] Unit test for date window + offline filters in `tests/unit/test_filters.py`
- [ ] T011 [P] Unit test for deduplication logic in `tests/unit/test_dedup.py`

### Storage Layer

- [ ] T012 [P] Implement Pydantic `EventDTO`, city enum, category slugs in `src/storage/schemas.py`
- [ ] T013 Implement SQLAlchemy models (Category, EventSource, Event, UserSettings) per `data-model.md` in `src/storage/models.py`
- [ ] T014 Implement async engine, session factory, `init`/`seed` CLI in `src/storage/database.py`
- [ ] T015 Implement event repository (query by city+category, by IDs, upsert) in `src/storage/repositories/events.py`
- [ ] T016 [P] Implement user settings repository in `src/storage/repositories/users.py`
- [ ] T017 Seed 6 categories + 2 event sources (yandex_afisha, kudago) in `src/storage/database.py`

### Scrapers

- [ ] T018 Implement `ScraperProtocol` and registry in `src/scrapers/base.py`
- [ ] T019 [P] Implement KudaGo API scraper per `contracts/scraper-interface.md` in `src/scrapers/kudago.py`
- [ ] T020 [P] Implement Yandex Afisha HTML scraper with rate limiting in `src/scrapers/yandex_afisha.py`
- [ ] T021 Implement sync runner (validate, filter, dedup, upsert) in `src/scrapers/runner.py`
- [ ] T022 Integration test for sync pipeline with mocked HTTP in `tests/integration/test_scraper_sync.py`

### Bot Shared Components

- [ ] T023 [P] Implement city and category inline keyboards per `contracts/bot-commands.md` in `src/bot/keyboards/menus.py`
- [ ] T024 [P] Implement event list/card message formatters in `src/bot/formatters/events.py`
- [ ] T025 Implement app config loader from `.env` in `src/config.py`

**Checkpoint**: Foundation ready — `python scripts/sync_events.py --city moscow` saves events; all Phase 2 tests pass

---

## Phase 3: User Story 1 — Подбор по категории (Priority: P1) 🎯 MVP

**Goal**: Онбординг (выбор города) + просмотр мероприятий по категории

**Independent Test**: `/start` → выбор города → «Концерты» → список ≤10 событий с названием, датой, местом (quickstart V1–V2)

### Tests for User Story 1

- [ ] T026 [P] [US1] Integration test for onboarding FSM in `tests/integration/test_bot_onboarding.py`

### Implementation for User Story 1

- [ ] T027 [US1] Implement FSM states and `/start` city onboarding in `src/bot/handlers/start.py`
- [ ] T028 [US1] Implement category browse handler and empty-state message in `src/bot/handlers/categories.py`
- [ ] T029 [US1] Wire handlers, FSM, middleware (user settings injection) in `src/bot/main.py`
- [ ] T030 [US1] Add `/categories` and `/help` commands in `src/bot/handlers/start.py`

**Checkpoint**: US1 fully functional — новый пользователь выбирает город и видит список по категории

---

## Phase 4: User Story 4 — Смена города в настройках (Priority: P2)

**Goal**: Пользователь меняет город через `/settings`

**Independent Test**: `/settings` → другой город → категория показывает события нового города (quickstart V5)

### Tests for User Story 4

- [ ] T031 [P] [US4] Integration test for city change in `tests/integration/test_bot_settings.py`

### Implementation for User Story 4

- [ ] T032 [US4] Implement `/settings` handler and city callback in `src/bot/handlers/settings.py`
- [ ] T033 [US4] Register settings handler and «⚙️ Настройки» button in `src/bot/keyboards/menus.py` and `src/bot/main.py`

**Checkpoint**: US4 complete — смена города влияет на все последующие запросы

---

## Phase 5: User Story 2 — ИИ-поиск (Priority: P2)

**Goal**: Текстовый запрос → ранжированный список мероприятий; fallback при недоступности ИИ

**Independent Test**: «джазовый концерт в эти выходные» → релевантные результаты; невалидный API key → fallback (quickstart V3–V4)

### Tests for User Story 2

- [ ] T034 [P] [US2] Unit tests for ranker (happy path, clarification, fallback) in `tests/unit/test_ai_ranker.py`

### Implementation for User Story 2

- [ ] T035 [P] [US2] Implement versioned prompts in `src/ai/prompts.py`
- [ ] T036 [P] [US2] Implement OpenAI client wrapper in `src/ai/client.py`
- [ ] T037 [US2] Implement retrieve-then-rank per `contracts/ai-assistant-contract.md` in `src/ai/ranker.py`
- [ ] T038 [US2] Implement free-text search handler with typing indicator in `src/bot/handlers/search.py`
- [ ] T039 [US2] Register search handler for non-command text messages in `src/bot/main.py`

**Checkpoint**: US2 complete — ИИ-поиск и fallback работают

---

## Phase 6: User Story 3 — Карточка мероприятия (Priority: P3)

**Goal**: Полная карточка события + кнопка «Назад» с сохранением контекста

**Independent Test**: Тап по событию из списка → карточка с ценой и ссылкой → «Назад» → прежний список (quickstart V2 step 3–4)

### Implementation for User Story 3

- [ ] T040 [US3] Implement event detail handler (`evt:` callback) in `src/bot/handlers/event_detail.py`
- [ ] T041 [US3] Implement list context storage for `back:list` navigation in `src/bot/handlers/event_detail.py`
- [ ] T042 [US3] Wire event callbacks from category and search result keyboards in `src/bot/handlers/categories.py` and `src/bot/handlers/search.py`

**Checkpoint**: US3 complete — полный путь от списка до карточки и обратно

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Фоновая синхронизация, документация, финальная валидация

- [ ] T043 [P] Add APScheduler daily sync job in `src/bot/main.py`
- [ ] T044 Complete `scripts/sync_events.py` CLI delegating to `src/scrapers/runner.py`
- [ ] T045 [P] Add stale-data notice in formatters when source sync failed in `src/bot/formatters/events.py`
- [ ] T046 [P] Create project `README.md` with setup link to `specs/001-ai-event-discovery/quickstart.md`
- [ ] T047 Run full quickstart.md validation scenarios and fix blockers

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational
- **US4 (Phase 4)**: Depends on US1 (user settings + main menu exist)
- **US2 (Phase 5)**: Depends on Foundational + US1 (main bot loop, event list formatters)
- **US3 (Phase 6)**: Depends on US1 (event list generates `evt:` callbacks)
- **Polish (Phase 7)**: Depends on US1–US3 desired for MVP demo

### User Story Dependencies

| Story | Depends on | Can start after |
|-------|------------|-----------------|
| US1 (P1) | Foundational | Phase 2 complete |
| US4 (P2) | US1 | Phase 3 complete |
| US2 (P2) | US1 | Phase 3 complete (parallel with US4) |
| US3 (P3) | US1 | Phase 3 complete (parallel with US4/US2) |

### Within Each User Story

- Tests MUST fail before implementation (TDD)
- Storage/repos before handlers
- Handlers before main.py wiring
- Story checkpoint before marking done

### Parallel Opportunities

**Phase 1**: T002, T003, T004, T005, T006 — parallel
**Phase 2**: T008–T011 (tests), T012+T016, T019+T020, T023+T024 — parallel groups
**After US1**: US4, US2, US3 can proceed in parallel by different developers

---

## Parallel Example: User Story 2

```bash
# Launch tests + AI modules together:
Task T034: "Unit tests for ranker in tests/unit/test_ai_ranker.py"
Task T035: "Prompts in src/ai/prompts.py"
Task T036: "OpenAI client in src/ai/client.py"
# Then sequential:
Task T037: "Ranker in src/ai/ranker.py" (depends on T035, T036)
Task T038: "Search handler in src/bot/handlers/search.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: quickstart V1–V2
5. Demo/deploy if ready

### Incremental Delivery

1. Setup + Foundational → база событий в БД
2. US1 → категории + онбординг (MVP!)
3. US4 → смена города
4. US2 → ИИ-поиск
5. US3 → карточки + навигация
6. Polish → scheduler + README

### Parallel Team Strategy

| Developer | Stories |
|-----------|---------|
| A | US1 → US3 (bot UI flow) |
| B | Phase 2 scrapers + runner |
| C | US2 (AI module) after Phase 2 |
| D | US4 after US1 |

---

## Task Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| Setup | T001–T007 | — |
| Foundational | T008–T025 | — |
| US1 (P1) | T026–T030 | 5 |
| US4 (P2) | T031–T033 | 3 |
| US2 (P2) | T034–T039 | 6 |
| US3 (P3) | T040–T042 | 3 |
| Polish | T043–T047 | — |
| **Total** | **47** | |

**Suggested MVP scope**: Phase 1 + Phase 2 + Phase 3 (US1) = 30 tasks
