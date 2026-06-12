# Research: ИИ-помощник для подбора мероприятий

**Date**: 2026-06-12 | **Branch**: `001-ai-event-discovery`

## 1. Telegram Bot Framework

**Decision**: aiogram 3.x

**Rationale**: Нативная async/await модель совместима с httpx-скраперами и
async SQLAlchemy без блокировки event loop. FSM (finite state machine) встроен
для онбординга (выбор города) и навигации «назад». Активное сообщество в RU-
сегменте.

**Alternatives considered**:
- *python-telegram-bot* — зрелый, но смешанная sync/async модель усложняет
  единый async pipeline
- *telebot/pyTelegramBotAPI* — проще, но слабее для FSM и async I/O

## 2. Database

**Decision**: SQLite (dev) + PostgreSQL via Supabase (prod/team)

**Rationale**: SQLite — нулевая настройка для локальной разработки и тестов.
PostgreSQL/Supabase — managed DB для команды, совместима с SQLAlchemy async,
поддерживает JSON-поля для метаданных источников.

**Alternatives considered**:
- *Только SQLite* — недостаточно для одновременной работы скрапера и бота в
  проде при нескольких инстансах
- *MongoDB* — избыточен для реляционной модели Event/UserSettings

## 3. Event Sources (Aggregators)

**Decision**: Яндекс Афиша (scraping) + KudaGo (REST API)

**Rationale**:
- **Яндекс Афиша** — обязательный источник по спецификации; HTML-страницы
  городских афиш парсятся через httpx + BeautifulSoup4 с rate limiting
  (1 req/s, User-Agent идентификация бота).
- **KudaGo** — публичный REST API (`https://kudago.com/public-api/v1.4/`),
  структурированные данные по городам, надёжнее скрапинга для второго
  источника (SC-004: 2 агрегатора).

**Alternatives considered**:
- *Afisha.ru scraping* — резервный третий источник post-MVP
- *Playwright для Яндекс Афиши* — отложен; сначала статический HTML парсинг

## 4. Scraper Architecture

**Decision**: Plugin pattern — каждый скрапер реализует `ScraperProtocol.fetch_events(city) -> list[EventDTO]`

**Rationale**: FR-004a требует добавление источников без изменения бота/ИИ.
Runner вызывает все зарегистрированные скраперы, нормализует, дедуплицирует,
upsert в БД.

**Alternatives considered**:
- *Монолитный парсер* — нарушает модульность и FR-004a
- *Отдельный микросервис скраперов* — избыточен для MVP

## 5. Deduplication

**Decision**: Двухуровневая дедупликация — (1) exact match по `source_url`;
(2) fuzzy match по нормализованному `title + start_date + venue` (порог
similarity ≥ 0.85, библиотека `rapidfuzz`).

**Rationale**: FR-010; одно событие на KudaGo и Яндекс Афише может иметь разные
URL. Fuzzy match ловит дубли без жёсткой связи ID.

**Alternatives considered**:
- *Только URL* — пропускает кросс-источниковые дубли
- *ML-кластеризация* — over-engineering для MVP

## 6. AI Provider

**Decision**: OpenAI API (`gpt-4o-mini`) через официальный `openai` SDK;
промпты версионированы в `src/ai/prompts.py` (`PROMPT_VERSION = "v1"`).

**Rationale**: Конституция требует OpenAI-compatible API; gpt-4o-mini — баланс
стоимости и качества для ранжирования ~50–200 кандидатов по запросу. При
недоступности — fallback на keyword + category filter (FR-007).

**Alternatives considered**:
- *Локальная LLM* — сложнее деплой, ниже качество на русском
- *Полный RAG* — избыточен; кандидаты уже отфильтрованы по городу/дате в БД

## 7. AI Ranking Flow

**Decision**: Retrieve-then-rank — SQL-фильтр (город, 30 дней, офлайн) → top-N
кандидатов (N≤100) → LLM возвращает JSON с `event_ids[]` и `clarification_needed`

**Rationale**: Укладывается в 10 с (FR-011); прозрачный контракт для тестов;
логируется `prompt_version`, `candidate_count`, `latency_ms`.

**Alternatives considered**:
- *Embedding search* — дополнительная инфраструктура, не нужна при N≤100
- *LLM генерирует ответ без привязки к ID* — риск галлюцинаций

## 8. Offline Event Detection

**Decision**: Фильтр на этапе нормализации — событие офлайн, если есть
физический `venue` и нет маркеров `online/stream/вебинар` в title/description;
KudaGo поле `place` не null.

**Rationale**: FR-003c; онлайн отсекается до попадания в БД.

## 9. Scheduler

**Decision**: APScheduler `AsyncIOScheduler` в процессе бота + `scripts/sync_events.py`

**Rationale**: Ежедневный cron (03:00 UTC) для FR-004; ручной запуск для отладки
и CI integration tests.

**Alternatives considered**:
- *Celery + Redis* — избыточная инфраструктура для MVP
- *systemd timer* — допустим в проде, но APScheduler проще для dev parity

## 10. City List (MVP)

**Decision**: 15 городов-миллионников + столицы республик (фиксированный enum в
`src/storage/schemas.py`): Москва, Санкт-Петербург, Новосибирск, Екатеринбург,
Казань, Нижний Новгород, Челябинск, Самара, Омск, Ростов-на-Дону, Уфа,
Красноярск, Воронеж, Пермь, Волгоград.

**Rationale**: Assumptions spec — минимум 10; 15 покрывает основную аудиторию;
slug маппится на параметры KudaGo и URL Яндекс Афиши.

## 11. CI/CD

**Decision**: GitHub Actions — `ruff check` + `pytest` на PR; секреты через
GitHub Environments.

**Rationale**: Constitution V — Team-First GitHub Workflow.
