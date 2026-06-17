# Bot Survey Flow Contract

**Version**: v2 | **Date**: 2026-06-14 | **Branch**: `002-multi-source-survey-flow`

Extends [001 bot-commands](../001-ai-event-discovery/contracts/bot-commands.md).

## Commands

| Command | Handler | Description |
|---------|---------|-------------|
| `/start` | `handlers/start.py` | City onboarding → main menu (4 main + ⚙️ Настройки) |
| `/settings` | `handlers/settings.py` | Change city |
| `/categories` | `handlers/categories.py` | **Deprecated** — hidden; not shown on main menu |
| `/help` | `handlers/start.py` | Usage hints |

## FSM States

| State | Trigger | Next |
|-------|---------|------|
| `ONBOARDING_CITY` | `/start`, no city | City selected → `MAIN_MENU` |
| `MAIN_MENU` | City set | Menu callbacks / free text → AI |
| `SURVEY_AUDIENCE` | `menu:survey` | Button → `SURVEY_ACTIVITY` |
| `SURVEY_ACTIVITY` | Audience chosen | Button → `SURVEY_BUDGET` |
| `SURVEY_BUDGET` | Activity chosen | Button → `SURVEY_FORMAT` |
| `SURVEY_FORMAT` | Budget chosen | Button → match → `SURVEY_RESULT` |
| `SURVEY_RESULT` | Card shown | next/fav/restart callbacks |
| `POPULAR_LIST` | `menu:popular` | open item / show more |
| `VIEWING_EVENT` | Event opened | Card actions |
| `FAVORITES_LIST` | `menu:favorites` | Open saved card |
| `AI_SEARCH` | Free text (not survey callback) | AI response |

## Main Menu Keyboard

After city selected:

| Button | callback_data |
|--------|---------------|
| 🎲 Случайный вариант | `menu:random` |
| 📝 Опрос | `menu:survey` |
| 🔥 Популярное | `menu:popular` |
| ❤️ Избранное | `menu:favorites` |

Optional row: `⚙️ Настройки` → `settings:open`

## Survey Step Keyboards

### Step 1 — Кто идёт?

| Label | callback_data |
|-------|---------------|
| 👤 Один | `survey:aud:solo` |
| 👫 Пара | `survey:aud:couple` |
| 👨‍👩‍👧‍👦 Семья | `survey:aud:family` |
| 👥 Друзья | `survey:aud:friends` |

### Step 2 — Категория активности

| Label | callback_data |
|-------|---------------|
| ⚽️ Спорт | `survey:act:sport` |
| 🎠 Для детей | `survey:act:kids` |
| 🏕 Семейный отдых | `survey:act:family` |
| 🎨 Культура | `survey:act:culture` |
| 🍽 Гастро | `survey:act:gastro` |
| 🧘 Релакс | `survey:act:relax` |

### Step 3 — Бюджет

| Label | callback_data |
|-------|---------------|
| 🆓 Бесплатно | `survey:bud:free` |
| 💵 до 1000₽ | `survey:bud:1000` |
| 💰 до 3000₽ | `survey:bud:3000` |
| 💎 Без лимита | `survey:bud:unlimited` |

### Step 4 — Погода / формат

| Label | callback_data |
|-------|---------------|
| 🌧 Только крытое | `survey:fmt:indoor` |
| ☀️ Всё равно | `survey:fmt:any` |
| 🏠 У дома | `survey:fmt:home` |

## Result Card Keyboard

| Label | callback_data | Context |
|-------|---------------|---------|
| ➡️ Другой вариант | `result:next` | Same filters / random pool |
| ❤️ В избранное | `result:fav:{event_id}` | Toggle or save |
| 🔄 Заново | `result:restart` | Survey → step 1; Random → main menu |

## Empty Results Keyboard

```text
😔 По вашим фильтрам ничего не нашлось.
```

| Label | callback_data |
|-------|---------------|
| Смягчить бюджет | `empty:budget` |
| Сменить формат | `empty:format` |
| 🔄 Заново | `empty:restart` |

## Popular List

Initial message: numbered list 1–5, inline buttons `popular:item:{event_id}` per row.

| Label | callback_data |
|-------|---------------|
| Показать ещё | `popular:more` |

After `popular:more`: extend list to 10 items (edit message).

## Message Template — Survey Result Card

```text
🤖 Для {audience_label} с бюджетом {budget_label}:

🧩 {title}
— {highlight_1}
— {highlight_2}
— Вход: {price_display}
— {format_display}

📍 {location_line}
🔗 [Подробнее]({source_url}) · [Навигатор]({maps_url})
```

## Free Text Routing

| Current state | Input type | Action |
|---------------|------------|--------|
| `SURVEY_*` | Text message | Clear survey FSM → `AI_SEARCH` |
| `SURVEY_*` | Matching callback | Advance survey |
| `MAIN_MENU`, `SURVEY_RESULT`, etc. | Text | `AI_SEARCH` |
| Any | Command | Command handler (priority) |

## Input Validation

| Input | Rule | Response |
|-------|------|----------|
| Empty text | Reject | «Напишите запрос или выберите кнопку меню» |
| Text > 500 chars | Truncate | Process first 500 chars |
| Sticker/photo | Reject | «Опишите текстом, что ищете» |

## Performance

- Callback handlers: p95 < 5 s (FR-016)
- `send_chat_action(typing)` on AI text input
- Popular list: single DB query, no LLM
