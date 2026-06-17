# Research: Мульти-источники и опросный подбор

**Date**: 2026-06-14 | **Branch**: `002-multi-source-survey-flow`

## 1. Survey UX & FSM

**Decision**: aiogram 3 FSM (`SurveyStates`) + inline-клавиатуры на каждом шаге; данные сессии в `FSMContext` (audience, activity, budget, format, `shown_event_ids[]`).

**Rationale**: Уже используется aiogram 3 и FSM в фиче 001 (`BotStates`). Опрос — 4 детерминированных шага с callback-only input (FR-017); не требует Redis/DB для черновика. «Другой вариант» хранит `shown_event_ids` в FSM до «Заново» или выхода в главное меню.

**Alternatives considered**:
- *DB-persisted survey draft* — избыточно; spec запрещает сохранение черновика при прерывании
- *ConversationHandler (python-telegram-bot)* — не применимо (другой фреймворк)

## 2. Rule-Based Survey Matcher vs AI

**Decision**: Подбор по опросу — **SQL-фильтры + эвристический score** в `src/ai/survey_matcher.py` (или `src/bot/services/survey_matcher.py`); ИИ **не обязателен** для опроса (FR-015). ИИ остаётся для свободного текста (US1b) через существующий `intent.py` + `ranker.py` / `places.py`.

**Rationale**: p95 < 5 с (FR-016) и детерминированность тестов; опрос имеет дискретные фильтры. LLM для 4 кнопок — overkill и риск 413/403.

**Alternatives considered**:
- *LLM ранжирует всех кандидатов после опроса* — медленнее, дороже, хуже тестируется
- *Только random из фильтра* — низкое качество релевантности

## 2b. AI Activity Classification at Ingest

**Decision**: При sync, если `activity_slug` не задан источником и rule-based classifier не дал результат — вызов `src/ai/activity_classifier.py` (одна категория из 6 значений опроса). Опрос пользователя остаётся rule-based (FR-022). При недоступности ИИ — только rule-based; событие сохраняется как «не классифицировано», повтор при следующей sync (FR-023).

**Rationale**: FR-021; события без категории в источнике должны участвовать в опросе после классификации; batch at sync дешевле и предсказуемее, чем LLM на каждый опрос.

**Alternatives considered**:
- *Только rule-based* — низкое покрытие на агрегаторах без категорий
- *LLM во время опроса* — нарушает FR-016/FR-022

## 3. Activity Categories (опрос) ↔ Event Taxonomy

**Decision**: Новое поле `activity_slug` на событии (enum из 6 значений опроса) + сохранение legacy `category_slug` из 001. Маппинг при ingest:

| activity_slug (опрос) | primary category_slug | ingest hints |
|----------------------|----------------------|--------------|
| `sport` | sport | moysportrayon, спортивные секции |
| `kids` | education, theater, other | детские, семейные теги в title/desc |
| `family` | other, exhibitions, sport | парки, квесты, zoо, family tags |
| `culture` | concerts, theater, exhibitions, education | афиши, МТПП форумы |
| `gastro` | other | food, ресторан, дегустация |
| `relax` | other, exhibitions | spa, йога, wellness (не спортивные тренировки) |

Нормализация: каждый скрапер → rule-based classifier → при null AI classifier at sync (§2b).

**Rationale**: FR-011 требует фильтр по категории активности; legacy категории 001 нужны для AI search и обратной совместимости.

**Alternatives considered**:
- *Заменить category_slug на activity_slug* — ломает 001 и AI prompts
- *Только LLM-классификация* — нестабильно без API

## 4. Venue Format & Budget Filtering

**Decision**: Новые поля `venue_format` (`indoor` | `outdoor` | `mixed` | `online` | `unknown`) и опционально `price_amount_rub` (int, мин. цена на человека, parsed). Фильтры опроса:

| Формат опроса | SQL filter |
|---------------|------------|
| Только крытое | `venue_format IN ('indoor', 'mixed')` |
| Всё равно | no filter |
| У дома | `venue_format = 'online'` OR `is_online = true` |

Бюджет: `free` → `price_type='free'`; `1000`/`3000` → `price_amount_rub IS NULL OR price_amount_rub <= N` (NULL не отсекается, помечается «уточняйте»).

**Rationale**: FR-020, edge cases по цене и indoor/outdoor. Ослабление `is_online=false` only для режима «У дома» (spec assumption).

**Alternatives considered**:
- *Фильтр только по price_text string* — ненадёжный parse

## 5. New Scraper Sources (Moscow-first)

**Decision**: Поэтапное подключение; единый `ScraperProtocol`; приоритет и метод:

| source_slug | Site | Method (MVP) | Notes |
|-------------|------|--------------|-------|
| `timepad` | afisha.timepad.ru | HTML/JSON-LD + возможный widget API | Структурированные страницы событий |
| `mts_live` | live.mts.ru | httpx + embedded JSON в HTML | Проверить `__NEXT_DATA__` / API |
| `tbank_gorod` | tbank.ru/gorod | httpx; при SPA-fail → Playwright task | Отложить Playwright в tasks если 403 |
| `mos_kultura` | mos.ru/kulturaonline | HTML list + detail pages | Rate limit 1 req/s |
| `timeout_msk` | timeout.ru/msk | HTML scraping | Афишные списки |
| `mos_sport_rayon` | moysportrayon.sport.mos.ru | HTML; recurring trainings as events | Бесплатно, sport/family |
| `mtpp` | mostpp.ru/events | HTML calendar | B2B → culture/education |
| `kudago` | existing | REST API | Already implemented |
| `yandex_afisha` | existing | HTML (best-effort) | May return 0; non-blocking |

**Rationale**: FR-007, FR-008; constitution III — plugin scrapers, isolated failures. Moscow-first снижает scope; 001 scrapers работают для 14 других городов.

**Alternatives considered**:
- *Playwright для всех SPA сразу* — тяжёлый деплой, нарушает MVP constraints 001
- *Один универсальный scraper* — нереалистично из-за разной вёрстки

## 6. Popularity Ranking

**Decision**: `popularity_score` вычисляется при sync/query:

```text
score = (30 - days_until_start) * 2
      + (source_count_in_dedup_group - 1) * 10
      + activity_weight[activity_slug]
```

Сортировка DESC, limit 10; UI отдаёт 5 + callback `popular:more`.

**Rationale**: FR-013, spec assumption (эвристики без закрытой аналитики).

**Alternatives considered**:
- *Telegram click tracking* — out of scope
- *Random «popular»* — не соответствует UX

## 7. Favorites Persistence

**Decision**: Таблица `favorites(telegram_id, event_id, saved_at)` с UNIQUE(telegram_id, event_id); repository `src/storage/repositories/favorites.py`.

**Rationale**: FR-014; простая реляционная модель, тестируемая.

**Alternatives considered**:
- *JSON в UserSettings* — плохо масштабируется и сложнее query

## 8. Free-Text → AI Routing

**Decision**: Router в `handlers/messages.py`: если `state in SurveyStates` и message is text (not callback) → reset survey FSM → delegate to existing `search.py` pipeline. Иначе free text → AI. Callback на шаге опроса → advance survey.

**Rationale**: FR-018, FR-019, US1b; переиспользует 001 AI stack.

**Alternatives considered**:
- *Отдельная команда /search* — пользователь явно отказался в clarify

## 9. Main Menu & Legacy /categories

**Decision**: Главное меню — 4 inline-кнопки (FR-001). `/categories` остаётся скрытой командой для отладки/ power users; не показывается на главном экране. Category browse handlers не удаляются в первой итерации — помечаются deprecated в plan/tasks.

**Rationale**: Clarify session + spec assumptions.

## 10. Card Formatter

**Decision**: Единый шаблон `format_survey_card(context, event)` в `src/bot/formatters/survey_card.py`:

```text
🤖 Для {audience_label} с бюджетом {budget_label}:
🧩 {title}
— {bullet1}
— {bullet2}
— Вход: {price}
— {venue_format_label}
📍 {address} · [Навигатор](yandex maps url)
```

Кнопки: `result:next`, `result:fav:{event_id}`, `result:restart` (контекст зависит от random/survey/popular).

**Rationale**: FR-004, FR-005; пример из user story.

**Alternatives considered**:
- *Разные форматтеры per flow* — дублирование
