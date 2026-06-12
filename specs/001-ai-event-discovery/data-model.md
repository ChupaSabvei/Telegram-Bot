# Data Model: ИИ-помощник для подбора мероприятий

**Date**: 2026-06-12 | **Branch**: `001-ai-event-discovery`

## Entity Relationship Overview

```text
UserSettings (1) ──< used by >── Telegram User (external: telegram_id)

EventSource (1) ──< provides >── Event (N)

Category (1) ──< classifies >── Event (N)

Event ── dedup_group_id ── Event (optional self-ref for merged duplicates)
```

## Entities

### Category

Справочник категорий (seed data, не редактируется пользователем в MVP).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | |
| slug | string | unique, not null | `concerts`, `exhibitions`, … |
| name_ru | string | not null | Отображаемое имя |
| description_ru | string | nullable | Подсказка в меню |
| sort_order | int | not null | Порядок кнопок |

**Seed slugs**: `concerts`, `exhibitions`, `theater`, `sport`, `education`, `other`

### EventSource

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | |
| slug | string | unique | `yandex_afisha`, `kudago` |
| name | string | not null | |
| base_url | string | not null | |
| source_type | enum | `aggregator` | |
| is_active | bool | default true | |
| last_sync_at | datetime | nullable | |
| last_sync_status | enum | `ok`, `error`, `partial` | |
| last_error | string | nullable | |

### Event

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | Internal ID |
| source_id | UUID | FK → EventSource | |
| external_id | string | nullable | ID в источнике |
| source_url | string | unique, not null | URL страницы события |
| dedup_group_id | UUID | nullable, indexed | Группа дублей |
| title | string | not null, max 500 | |
| description | text | nullable | |
| category_id | UUID | FK → Category | |
| city_slug | string | not null, indexed | `moscow`, `spb`, … |
| venue | string | nullable | Офлайн-площадка |
| start_at | datetime | not null, indexed | TZ-aware (UTC stored) |
| end_at | datetime | nullable | |
| price_type | enum | `free`, `paid`, `unknown` | FR-005 |
| price_text | string | nullable | «от 1500 ₽» |
| is_online | bool | default false | Must be false in DB (FR-003c) |
| image_url | string | nullable | |
| synced_at | datetime | not null | |
| created_at | datetime | not null | |
| updated_at | datetime | not null | |

**Validation rules**:
- `start_at` MUST be > now() AND <= now() + 30 days для отображения (FR-009)
- `is_online` MUST be `false` при insert/update
- `venue` SHOULD be non-empty для офлайн-событий

**Indexes**: `(city_slug, category_id, start_at)`, `(dedup_group_id)`, `(source_url)`

### UserSettings

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| telegram_id | bigint | PK | Telegram user ID |
| city_slug | string | not null | Выбранный город |
| onboarding_complete | bool | default false | Город выбран |
| updated_at | datetime | not null | |

**State transitions**:
1. New user → `onboarding_complete=false`, `city_slug` unset → prompt city
2. City selected → `onboarding_complete=true`, `city_slug` set
3. Settings change → `city_slug` updated, `updated_at` bumped

### UserQuery (ephemeral / log, optional MVP)

Логирование для отладки ИИ; не обязательно в MVP schema — можно structured log.
Если добавляется:

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| telegram_id | bigint | |
| query_text | string | max 500 |
| category_slug | string | nullable |
| created_at | datetime | |

## City Slug Reference

| city_slug | name_ru | KudaGo location | Yandex Afisha path |
|-----------|---------|-----------------|-------------------|
| moscow | Москва | `msk` | `moscow` |
| spb | Санкт-Петербург | `spb` | `saint-petersburg` |
| novosibirsk | Новосибирск | `nsk` | `novosibirsk` |
| yekaterinburg | Екатеринбург | `ekb` | `yekaterinburg` |
| kazan | Казань | `kzn` | `kazan` |
| nizhny_novgorod | Нижний Новгород | `nn` | `nizhny-novgorod` |
| chelyabinsk | Челябинск | `chl` | `chelyabinsk` |
| samara | Самара | `smr` | `samara` |
| omsk | Омск | `omsk` | `omsk` |
| rostov_on_don | Ростов-на-Дону | `rnd` | `rostov-on-don` |
| ufa | Уфа | `ufa` | `ufa` |
| krasnoyarsk | Красноярск | `krs` | `krasnoyarsk` |
| voronezh | Воронеж | `vrn` | `voronezh` |
| perm | Пермь | `perm` | `perm` |
| volgograd | Волгоград | `vlg` | `volgograd` |

## Deduplication Logic

1. **Exact**: `source_url` unique constraint prevents re-insert
2. **Cross-source**: при sync, если `rapidfuzz.token_sort_ratio(title) >= 85`
   AND `start_at` same day AND same `city_slug` AND similar `venue` → assign
   same `dedup_group_id`; в выдаче показывается одна карточка (приоритет:
   более полное описание, затем более свежий `synced_at`)

## Query Patterns

### Category browse (US1)

```sql
SELECT * FROM events
WHERE city_slug = :user_city
  AND category_id = :category
  AND start_at > NOW()
  AND start_at <= NOW() + INTERVAL '30 days'
  AND is_online = false
ORDER BY start_at ASC
LIMIT 10;
```

### AI search candidates (US2)

```sql
SELECT id, title, description, category_id, start_at, venue, price_text
FROM events
WHERE city_slug = :user_city
  AND start_at > NOW()
  AND start_at <= NOW() + INTERVAL '30 days'
  AND is_online = false
ORDER BY start_at ASC
LIMIT 100;
```

→ передать в `ai.ranker.rank(query, candidates)`
