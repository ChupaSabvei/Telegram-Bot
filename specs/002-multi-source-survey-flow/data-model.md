# Data Model: Мульти-источники и опросный подбор

**Date**: 2026-06-14 | **Branch**: `002-multi-source-survey-flow`

Extends [001 data-model](../001-ai-event-discovery/data-model.md).

## Entity Relationship Overview

```text
UserSettings (1) ──< favorites >── Favorite (N) ──> Event (1)

EventSource (1) ──< provides >── Event (N)

Event ── dedup_group_id ── Event

SurveySession — ephemeral (aiogram FSM, not persisted)
```

## Schema Changes (002)

### Event — new / changed fields

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| activity_slug | enum | nullable until classified | `sport`, `kids`, `family`, `culture`, `gastro`, `relax`; null = «не классифицировано» (excluded from survey) |
| venue_format | enum | default `unknown` | `indoor`, `outdoor`, `mixed`, `online`, `unknown` |
| price_amount_rub | int | nullable | Parsed min price per person |
| audience_tags | JSON array | default `[]` | e.g. `["family", "kids"]` |
| address | string | nullable | Full address if available (navigator link) |
| popularity_score | int | default 0, not null | Computed at sync; used for popular list and survey tie-break (see research §6) |
| is_online | bool | default false | **Changed**: may be `true` for online/at-home events |

**Migration**: Alembic/SQLAlchemy migration adds columns with defaults; backfill `activity_slug` from `category_slug` mapping for existing rows.

### EventSource — extended slugs

| slug | name | city_scope |
|------|------|------------|
| `timepad` | Timepad Afisha | moscow (MVP) |
| `mts_live` | MTS Live | moscow |
| `tbank_gorod` | T-Bank Город | moscow |
| `mos_kultura` | Культура Москвы | moscow |
| `timeout_msk` | Time Out Москва | moscow |
| `mos_sport_rayon` | Мой спортивный район | moscow |
| `mtpp` | МТПП Календарь | moscow |
| `kudago` | KudaGo | all MVP cities |
| `yandex_afisha` | Яндекс Афиша | all MVP cities |

### Favorite (new)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | |
| telegram_id | bigint | FK logical → UserSettings | |
| event_id | UUID | FK → Event, ON DELETE CASCADE | |
| saved_at | datetime | not null | |
| UNIQUE | | (telegram_id, event_id) | Prevent duplicate saves |

**Behavior**: On list favorites, JOIN Event; if `start_at < now()` → UI badge «завершилось».

### SurveySession (FSM — not DB)

Stored in `FSMContext.data`:

| Key | Type | Notes |
|-----|------|-------|
| `audience` | enum | `solo`, `couple`, `family`, `friends` |
| `activity` | enum | 6 activity slugs |
| `budget` | enum | `free`, `1000`, `3000`, `unlimited` |
| `format` | enum | `indoor`, `any`, `home` |
| `shown_event_ids` | list[UUID] | For «Другой вариант» |
| `flow` | enum | `survey`, `random`, `popular` — affects «Заново» target |

**State transitions**:

```text
MAIN_MENU
  → [📝 Опрос] → SURVEY_AUDIENCE → SURVEY_ACTIVITY → SURVEY_BUDGET → SURVEY_FORMAT
  → SURVEY_RESULT (card shown)
  → [Другой вариант] → SURVEY_RESULT (next id)
  → [Заново] → SURVEY_AUDIENCE
  → [text during survey] → reset → AI_SEARCH

MAIN_MENU
  → [🎲 Случайный] → SURVEY_RESULT (flow=random, no survey fields)
  → [Заново] → MAIN_MENU

MAIN_MENU
  → [🔥 Популярное] → POPULAR_LIST (5 items)
  → [Показать ещё] → POPULAR_LIST (10 items)
  → [item N] → VIEWING_EVENT (full card)
```

## Survey Filter Query (conceptual)

```sql
SELECT e.* FROM events e
WHERE e.city_slug = :city
  AND e.start_at > NOW()
  AND e.start_at <= NOW() + INTERVAL '30 days'
  AND e.activity_slug = :activity
  AND (:audience_filter)          -- audience_tags overlap
  AND (:budget_filter)            -- price_type / price_amount_rub
  AND (:format_filter)            -- venue_format / is_online
  AND e.id NOT IN (:shown_ids)
ORDER BY start_at ASC, popularity_score DESC
LIMIT 1;
```

### Empty-result softening (FR-020)

| User action | Effect |
|-------------|--------|
| Смягчить бюджет | Bump budget tier one step (1000→3000→unlimited); re-query |
| Сменить формат | Set format=`any`; re-query |
| Заново | Clear FSM → SURVEY_AUDIENCE |

## Activity Classifier Rules (ingest)

Pipeline in `src/scrapers/runner.py` (FR-021, FR-023):

1. **Source mapping** — category/tags from scraper DTO if present
2. **Rule-based** — `src/scrapers/classifiers/activity.py` (keywords, source_slug)
3. **AI fallback** — `src/ai/activity_classifier.py` if step 2 yields null (title, description, source, city)
4. **Unclassified** — save with `activity_slug = null`; retry steps 2–3 on next sync; sync MUST NOT abort if AI unavailable (FR-023)

Rule engine highlights in `activity.py`:

- `mos_sport_rayon` → `activity_slug=sport`, `price_type=free`, `venue_format=outdoor|mixed`
- `mtpp` → `activity_slug=culture`, `audience_tags=[]` (B2B)
- Title contains «дет» → add `kids` to audience_tags, bias `activity_slug=kids`
- Source category «концерт» → `culture`

## Indexes (new)

- `(city_slug, activity_slug, start_at)`
- `(telegram_id, saved_at)` on favorites

## Backward Compatibility

- `category_slug` retained for AI search and `/categories`
- Events without `activity_slug` excluded from survey matcher; MAY appear in «Случайный» and «Популярное»; runner retries classification each sync; one-time backfill for legacy KudaGo rows (T054)
- `EventDTO` in pydantic v2 extended; contract `event-schema-v2.json`
