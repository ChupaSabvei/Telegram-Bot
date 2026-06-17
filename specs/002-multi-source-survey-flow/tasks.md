---
description: "Task list for Мульти-источники и опросный подбор"
---

# Tasks: Мульти-источники и опросный подбор

**Input**: Design documents from `specs/002-multi-source-survey-flow/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Включены — конституция v1.0.0 требует TDD для скраперов, схем, matcher и хендлеров бота.

**Organization**: Задачи сгруппированы по user story для независимой реализации и тестирования.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Можно выполнять параллельно (разные файлы, нет зависимостей от незавершённых задач)
- **[Story]**: US1, US1b, US2, US3, US4, US5 — user stories из spec.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Подготовка инфраструктуры для фичи 002 поверх существующего проекта 001

- [x] T001 [P] Create scraper HTML fixtures directory and README in `tests/fixtures/html/README.md`
- [x] T002 [P] Add Moscow event count CLI for SC-002 gate in `scripts/count_events.py`
- [x] T003 Add schema migration 002 (Event v2 columns + favorites table) in `src/storage/migrations/002_survey_flow.sql` and wire in `src/storage/database.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Схема данных, matcher, клавиатуры, formatter — MUST завершить до user stories

**⚠️ CRITICAL**: User story work cannot begin until this phase is complete

### Tests First (TDD — must FAIL before implementation)

- [x] T004 [P] Contract test EventDTO v2 vs `specs/002-multi-source-survey-flow/contracts/event-schema-v2.json` in `tests/contract/test_event_schema_v2.py`
- [x] T005 [P] Unit tests for survey_matcher per `specs/002-multi-source-survey-flow/contracts/survey-matcher-contract.md` in `tests/unit/test_survey_matcher.py`
- [x] T006 [P] Unit tests for survey card formatter in `tests/unit/test_survey_card.py`

### Storage & Services

- [x] T007 Extend EventDTO v2 enums and fields in `src/storage/schemas.py`
- [x] T008 Add Favorite model and Event 002 columns per `data-model.md` in `src/storage/models.py`
- [x] T009 Seed 7 new EventSource rows (timepad, mts_live, etc.) in `src/storage/database.py`
- [x] T010 Extend event repository with survey/random/popular queries in `src/storage/repositories/events.py`
- [x] T011 Implement favorites repository in `src/storage/repositories/favorites.py`
- [x] T012 [P] Unit tests AI activity classifier (FR-021/FR-023) in `tests/unit/test_activity_classifier.py`
- [x] T013 Implement AI activity classifier in `src/ai/activity_classifier.py`
- [x] T014 Implement rule-based activity classifier in `src/scrapers/classifiers/activity.py`
- [x] T015 Implement survey_matcher service in `src/bot/services/survey_matcher.py`

### Bot Shared Components (002)

- [x] T016 [P] Implement main menu keyboard (4 main buttons + ⚙️ Настройки) per `contracts/bot-survey-flow.md` in `src/bot/keyboards/main_menu.py`
- [x] T017 [P] Implement survey step keyboards in `src/bot/keyboards/survey.py`
- [x] T018 [P] Implement unified survey card formatter in `src/bot/formatters/survey_card.py`
- [x] T019 Extend FSM with SurveyStates and PopularStates in `src/bot/states.py`
- [x] T020 Extend runner: v2 upsert, popularity_score, classify pipeline (rule → AI → unclassified retry) per FR-021/023 in `src/scrapers/runner.py`

**Checkpoint**: Foundation ready — matcher unit tests pass; DB migrates; repositories queryable

---

## Phase 3: User Story 1 — Опросный подбор (Priority: P1) 🎯 MVP

**Goal**: Город → 4 основные кнопки + ⚙️ Настройки → опрос 4 шага → персонализированная карточка + empty state

**Independent Test**: quickstart V1–V2, V4 — «Семья → Семейный отдых → 3000₽ → Всё равно» → карточка с 3 action-кнопками

### Tests for User Story 1

- [x] T021 [P] [US1] Integration test survey FSM in `tests/integration/test_survey_fsm.py`

### Implementation for User Story 1

- [x] T022 [US1] Refactor start handler: city onboarding, 5-button main menu, settings (change city) in `src/bot/handlers/start.py`
- [x] T023 [US1] Implement survey handler (4 steps + result card) in `src/bot/handlers/survey.py`
- [x] T024 [US1] Implement result callbacks (next/fav/restart) and empty-state softening in `src/bot/handlers/survey.py`
- [x] T025 [US1] Register menu:survey, menu:settings and survey:* callbacks in `src/bot/main.py`

**Checkpoint**: US1 complete — опрос end-to-end работает на данных KudaGo (до новых scrapers)

---

## Phase 4: User Story 1b — ИИ на свободный текст (Priority: P1)

**Goal**: Произвольный текст активирует ИИ; текст на шаге опроса сбрасывает FSM

**Independent Test**: quickstart V8 — «бильярд рядом» на главном меню → AI; текст mid-survey → AI + reset

### Tests for User Story 1b

- [x] T026 [P] [US1b] Integration test free-text router in `tests/integration/test_free_text_router.py`

### Implementation for User Story 1b

- [x] T027 [US1b] Implement messages router delegating to `search.py` in `src/bot/handlers/messages.py`
- [x] T028 [US1b] Register messages handler with survey-state guard in `src/bot/main.py`

**Checkpoint**: US1b complete — free text → existing AI pipeline; survey callbacks unaffected

---

## Phase 5: User Story 2 — Агрегация из множества источников (Priority: P1)

**Goal**: 7 новых Moscow scrapers + classifier; SC-002: ≥200 events, ≥5 sources

**Independent Test**: quickstart sync + V9 — `python scripts/sync_events.py --city moscow` → ≥5 sources with saved > 0

### Tests for User Story 2

- [x] T029 [P] [US2] Unit test Timepad parser fixture in `tests/unit/scrapers/test_timepad.py`
- [x] T030 [P] [US2] Unit test MTS Live parser fixture in `tests/unit/scrapers/test_mts_live.py`
- [x] T031 [P] [US2] Unit test Мой спортивный район parser fixture in `tests/unit/scrapers/test_mos_sport_rayon.py`
- [x] T032 [P] [US2] Unit test T-Bank Gorod parser fixture in `tests/unit/scrapers/test_tbank_gorod.py`
- [x] T033 [P] [US2] Unit test Time Out parser fixture in `tests/unit/scrapers/test_timeout_msk.py`
- [x] T034 [P] [US2] Unit test mos.ru kultura parser fixture in `tests/unit/scrapers/test_mos_kultura.py`
- [x] T035 [P] [US2] Unit test MTTP parser fixture in `tests/unit/scrapers/test_mtpp.py`

### Implementation for User Story 2

- [x] T036 [P] [US2] Implement Timepad scraper per `contracts/scraper-sources.md` in `src/scrapers/timepad.py`
- [x] T037 [P] [US2] Implement MTS Live scraper in `src/scrapers/mts_live.py`
- [x] T038 [P] [US2] Implement Мой спортивный район scraper in `src/scrapers/mos_sport_rayon.py`
- [x] T039 [P] [US2] Implement T-Bank Gorod scraper in `src/scrapers/tbank_gorod.py`
- [x] T040 [P] [US2] Implement Time Out Moscow scraper in `src/scrapers/timeout_msk.py`
- [x] T041 [P] [US2] Implement mos.ru Kultura scraper in `src/scrapers/mos_kultura.py`
- [x] T042 [US2] Implement MTTP calendar scraper in `src/scrapers/mtpp.py`
- [x] T043 [US2] Register all new scrapers in `src/scrapers/runner.py`
- [x] T044 [US2] Integration test Moscow sync SC-002 gate in `tests/integration/test_moscow_sync.py`

**Checkpoint**: US2 complete — Moscow sync ≥200 unique events from ≥5 sources

---

## Phase 6: User Story 3 — Случайный вариант (Priority: P2)

**Goal**: «🎲 Случайный вариант» → одна карточка; «Заново» → главное меню

**Independent Test**: quickstart V5 — random card < 5 s; restart returns to main menu

### Tests for User Story 3

- [x] T045 [P] [US3] Unit test random event selection in `tests/unit/test_random_pick.py`

### Implementation for User Story 3

- [x] T046 [US3] Implement random variant handler in `src/bot/handlers/random.py`
- [x] T047 [US3] Register menu:random callback in `src/bot/main.py`

**Checkpoint**: US3 complete — random flow independent of survey

---

## Phase 7: User Story 4 — Популярное (Priority: P2)

**Goal**: Список 5 пунктов + «Показать ещё» до 10; tap → полная карточка

**Independent Test**: quickstart V6 — 5 items, show more, open full card

### Tests for User Story 4

- [x] T048 [P] [US4] Unit test popular query pagination in `tests/unit/test_popular_query.py`

### Implementation for User Story 4

- [x] T049 [US4] Implement popular list handler in `src/bot/handlers/popular.py`
- [x] T050 [US4] Register menu:popular and popular:* callbacks in `src/bot/main.py`

**Checkpoint**: US4 complete — popular list and drill-down work

---

## Phase 8: User Story 5 — Избранное (Priority: P3)

**Goal**: Сохранение с карточки; просмотр через «❤️ Избранное» на главном меню

**Independent Test**: quickstart V7 — save, list, survives bot restart

### Tests for User Story 5

- [x] T051 [P] [US5] Integration test favorites persistence in `tests/integration/test_favorites.py`

### Implementation for User Story 5

- [x] T052 [US5] Implement favorites list and open handlers in `src/bot/handlers/favorites.py`
- [x] T053 [US5] Wire result:fav save and menu:favorites in `src/bot/handlers/favorites.py` and `src/bot/main.py`

**Checkpoint**: US5 complete — favorites CRUD end-to-end

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Backfill, docs, validation, cleanup

- [x] T054 [P] One-time backfill activity_slug for legacy KudaGo rows in `scripts/backfill_activity.py` (ongoing retry via T020 runner)
- [x] T055 [P] Update README.md with 002 UX flows and Moscow sources in `README.md`
- [x] T056 Remove category grid from main menu display (keep `/categories` handler) in `src/bot/handlers/start.py`
- [x] T057 Run full `specs/002-multi-source-survey-flow/quickstart.md` validation and fix blockers
- [x] T058 [P] Verify CI covers new test paths in `.github/workflows/ci.yml`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational
- **US1b (Phase 4)**: Depends on US1 (main menu + survey FSM exist)
- **US2 (Phase 5)**: Depends on Foundational; **can parallel with US1/US1b** (different modules)
- **US3 (Phase 6)**: Depends on Foundational + US1 (shared card formatter)
- **US4 (Phase 7)**: Depends on Foundational + US1 (card formatter)
- **US5 (Phase 8)**: Depends on Foundational + US1 (result:fav callback)
- **Polish (Phase 9)**: Depends on US1–US5 desired for release

### User Story Dependencies

| Story | Depends on | Can start after |
|-------|------------|-----------------|
| US1 (P1) | Foundational | Phase 2 complete |
| US1b (P1) | US1 | Phase 3 complete |
| US2 (P1) | Foundational | Phase 2 complete (parallel with US1) |
| US3 (P2) | US1 | Phase 3 complete |
| US4 (P2) | US1 | Phase 3 complete |
| US5 (P3) | US1 | Phase 3 complete |

### Within Each User Story

- Tests MUST fail before implementation (TDD)
- Repositories/services before handlers
- Handlers before `main.py` wiring
- Story checkpoint before next priority

### Parallel Opportunities

**Phase 1**: T001, T002 — parallel  
**Phase 2**: T004–T006 (tests), T012 (AI classifier tests), T016–T018 (keyboards/formatter) — parallel groups  
**Phase 5 US2**: T029–T035 (tests), T036–T041 (scrapers) — parallel per file  
**After US1**: US3, US4, US5 can proceed in parallel  

---

## Parallel Example: User Story 2 (Scrapers)

```bash
# Launch all scraper unit tests + implementations in parallel (different files):
Task T029: tests/unit/scrapers/test_timepad.py
Task T036: src/scrapers/timepad.py
Task T030: tests/unit/scrapers/test_mts_live.py
Task T037: src/scrapers/mts_live.py
Task T031: tests/unit/scrapers/test_mos_sport_rayon.py
Task T038: src/scrapers/mos_sport_rayon.py
# Then sequential integration:
Task T043: src/scrapers/runner.py
Task T044: tests/integration/test_moscow_sync.py
```

---

## Parallel Example: User Story 1

```bash
# After Phase 2 complete:
Task T021: tests/integration/test_survey_fsm.py
Task T022: src/bot/handlers/start.py
Task T023: src/bot/handlers/survey.py  # after T021 fails
```

---

## Implementation Strategy

### MVP First (Survey on existing data)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (опрос)
4. Complete Phase 4: User Story 1b (ИИ текст)
5. **STOP and VALIDATE**: quickstart V1–V2, V4, V8
6. Demo with KudaGo data while US2 scrapers land

### Incremental Delivery

1. Setup + Foundational → schema + matcher ready
2. US1 + US1b → новый UX + AI (MVP demo!)
3. US2 → наполнение базы (SC-002)
4. US3 + US4 + US5 → случайный, популярное, избранное
5. Polish → README + full quickstart

### Parallel Team Strategy

| Developer | Stories |
|-----------|---------|
| A | Phase 2 bot layer → US1 → US1b → US3/US4/US5 |
| B | Phase 2 scraper layer → US2 (all scrapers) |
| C | Tests + integration (T004–T006, T012, T021, T044) |

---

## Task Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| Setup | T001–T003 | — |
| Foundational | T004–T020 | — |
| US1 (P1) | T021–T025 | 5 |
| US1b (P1) | T026–T028 | 3 |
| US2 (P1) | T029–T044 | 16 |
| US3 (P2) | T045–T047 | 3 |
| US4 (P2) | T048–T050 | 3 |
| US5 (P3) | T051–T053 | 3 |
| Polish | T054–T058 | — |
| **Total** | **58** | |

**Suggested MVP scope**: Phase 1 + Phase 2 + Phase 3 + Phase 4 = **28 tasks** (опрос + ИИ текст + ingest classifier на KudaGo)

**Suggested release scope**: MVP + Phase 5 (US2) = **44 tasks** (полная база Moscow)

---

## Notes

- User Story 1b labeled `[US1b]` — P1 companion to US1 per spec.md
- `/categories` остаётся, но не на главном экране (T056)
- FR-021/023: T012–T014 (classifiers), T020 (runner pipeline); T054 — one-time legacy backfill
- Yandex Afisha best-effort; SC-002 satisfied by other sources
- Playwright for SPA sources — only if httpx fails; track in US2 task comments
