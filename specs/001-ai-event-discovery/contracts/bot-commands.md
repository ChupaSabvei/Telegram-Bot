# Telegram Bot UI Contract

**Version**: v1 | **Date**: 2026-06-12

## Commands

| Command | Handler | Description |
|---------|---------|-------------|
| `/start` | `handlers/start.py` | Onboarding or main menu |
| `/categories` | `handlers/categories.py` | Category picker |
| `/settings` | `handlers/settings.py` | Change city |
| `/help` | `handlers/start.py` | Usage hints |

## FSM States

| State | Trigger | Next |
|-------|---------|------|
| `ONBOARDING_CITY` | First `/start`, no city saved | City selected → `MAIN_MENU` |
| `MAIN_MENU` | City set | Category / text search |
| `BROWSING_CATEGORY` | Category button | Event list |
| `VIEWING_EVENT` | Event button | Event card |
| `SETTINGS_CITY` | `/settings` | City changed → `MAIN_MENU` |
| `AI_SEARCH` | Free text (not command) | Ranked results |

## Callback Data Format

Prefix-based, max 64 bytes (Telegram limit):

| Pattern | Example | Action |
|---------|---------|--------|
| `city:{slug}` | `city:moscow` | Save city (onboarding/settings) |
| `cat:{slug}` | `cat:concerts` | List events in category |
| `evt:{uuid}` | `evt:a1b2c3...` | Show event card |
| `back:list` | `back:list` | Return to previous list |
| `back:menu` | `back:menu` | Return to main menu |

## Message Templates

### Main menu (after onboarding)

```text
📍 Город: {city_name}

Выберите категорию или напишите, что хотите посетить.
```

Inline keyboard: 6 category buttons + «⚙️ Настройки»

### Event list (max 10)

```text
🎭 {category_name} в {city_name}:

1. {title} — {date_short}, {venue_short}
...
```

Each item: inline button `evt:{uuid}`

### Event card

```text
📌 {title}

📅 {date_full}
📍 {venue}
💰 {price_display}
🏷 {category_name}

{description_truncated_300}

🔗 Подробнее на сайте
```

Buttons: `[🔗 Открыть]` (URL), `[◀️ Назад]`

### Empty category

```text
В категории «{category_name}» пока нет мероприятий на ближайший месяц.
Попробуйте другую категорию.
```

### AI clarification

```text
Уточните, пожалуйста: какой тип мероприятия или дату вы ищете?
Или выберите категорию из меню.
```

### Stale data notice (edge case)

```text
ℹ️ Данные обновлены {sync_date}. Некоторые источники временно недоступны.
```

## Input Validation

| Input | Rule | Response |
|-------|------|----------|
| Empty text | Reject | «Напишите запрос или выберите категорию» |
| Text > 500 chars | Truncate + warn | Process first 500 chars |
| Non-text (sticker/photo) | Reject | «Пожалуйста, опишите текстом» |

## Performance

- Все handler'ы MUST отвечать `answer`/`edit` в течение 10 с (FR-011)
- Долгие операции (AI): `send_chat_action(typing)` сразу при получении текста
