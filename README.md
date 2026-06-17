# Afisha AI — Telegram Event Bot

ИИ-помощник в Telegram для подбора офлайн-досуга: мероприятия из афиши, текстовый поиск и рекомендации мест (бильярд, боулинг, пляжи и т.д.).

**Бот:** [@Afisha_ai_bot](https://t.me/Afisha_ai_bot)

---

## Возможности (002)

| Режим | Как пользоваться | Что получает пользователь |
|-------|------------------|---------------------------|
| **Главное меню** | `/start` → выбор города | 🎲 Случайный · 📝 Опрос · 🔥 Популярное · ❤️ Избранное · ⚙️ Настройки |
| **Опрос** | 📝 Опрос → 4 шага (кнопки) | Персонализированная карточка + «Другой вариант» / «В избранное» / «Заново» |
| **Случайный** | 🎲 Случайный вариант | Одна карточка из города |
| **Популярное** | 🔥 Популярное | 5 пунктов + «Показать ещё» (до 10) |
| **Избранное** | ❤️ на карточке / меню | Сохранённые события между сессиями |
| **ИИ-помощник** | Произвольный текст в чат | Поиск мероприятий и мест (как в 001) |
| **Legacy категории** | `/categories` | Сетка категорий 001 (скрыта с главного экрана) |

### Источники данных и города

- **Универсальные (15 городов):** KudaGo, Яндекс Афиша, Timepad, MTS Live, T-Bank Город.
- **Только Москва (city-locked):** Культура Москвы, Time Out Москва, Мой спортивный район, МТПП.

```bash
python scripts/sync_events.py --city moscow
python scripts/sync_events.py --all-cities
python scripts/count_events.py --city moscow --min-events 200 --min-sources 5
python scripts/count_events.py --all-cities --min-events 30 --min-sources 2
python scripts/backfill_activity.py     # legacy activity_slug backfill
```

---

## Возможности (001 — legacy)

| Режим | Как пользоваться | Что получает пользователь |
|-------|------------------|---------------------------|
| **Категории** | Кнопки после `/start` | До 20 ближайших событий: концерты, театр, выставки, спорт, образование |
| **Карточка события** | Кнопка с названием | Дата, место, цена, описание, ссылка на источник |
| **ИИ-поиск по афише** | Текст: «джаз в эти выходные» | Подборка релевантных мероприятий из базы |
| **ИИ-подбор мест** | Текст: «куда сходить на бильярд» | Список заведений/локаций со ссылками на Яндекс.Карты |
| **Настройки** | `/settings` или кнопка «⚙️ Настройки» | Смена города (15 городов России) |

Горизонт подбора событий — **30 дней** вперёд от текущей даты.

---

## Стек

| Компонент | Технология |
|-----------|------------|
| Bot framework | [aiogram 3](https://docs.aiogram.dev/) |
| HTTP / scraping | httpx, BeautifulSoup4 |
| БД | SQLAlchemy 2 (async), SQLite (dev) / PostgreSQL (prod) |
| ИИ | OpenAI-compatible API ([Groq](https://groq.com) по умолчанию) |
| Планировщик | APScheduler (ночная синхронизация в 03:00) |
| Тесты | pytest, ruff |

**Python:** 3.11+

---

## Быстрый старт

### 1. Клонирование и окружение

```bash
git clone <url-репозитория>
cd "Телеграм БОТ"

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Переменные окружения

```bash
cp .env.example .env
```

Заполните `.env`:

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `BOT_TOKEN` | да | Токен от [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY` | да | API-ключ LLM (Groq, OpenAI и др.) |
| `OPENAI_API_BASE` | нет | Base URL для совместимого API. Для Groq: `https://api.groq.com/openai/v1` |
| `OPENAI_MODEL` | нет | Модель, напр. `llama-3.3-70b-versatile` |
| `DATABASE_URL` | нет | По умолчанию SQLite: `sqlite+aiosqlite:///./data/bot.db` |
| `TELEGRAM_PROXY` | нет | SOCKS5-прокси, если `api.telegram.org` недоступен |

Пример для Groq:

```env
BOT_TOKEN=123456:ABC...
OPENAI_API_KEY=gsk_...
OPENAI_API_BASE=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
```

> **Не коммитьте `.env` в git** — файл уже в `.gitignore`.

### 3. База данных

```bash
python -m src.storage.database init
python -m src.storage.database seed
```

`seed` создаёт 6 категорий и 2 источника данных (KudaGo, Яндекс Афиша).

### 4. Загрузка событий

```bash
# Москва (отладка)
python scripts/sync_events.py --city moscow

# Все города MVP
python scripts/sync_events.py --all-cities
```

Ожидаемый результат для Москвы: `kudago saved=100+`. Яндекс Афиша часто возвращает `0` из‑за captcha/403 с локального IP — это нормально, основной источник — **KudaGo**.

### 5. Запуск бота

```bash
python -m src.bot.main
```

В логе должно появиться:

```text
INFO:aiogram.dispatcher:Start polling
INFO:aiogram.dispatcher:Run polling for bot @...
```

Откройте бота в Telegram и отправьте `/start`.

---

## Использование

### Команды

| Команда | Описание |
|---------|----------|
| `/start` | Онбординг (выбор города) или главное меню |
| `/categories` | Список категорий |
| `/settings` | Сменить город |
| `/help` | Краткая справка |

### Текстовые запросы (ИИ)

Бот автоматически определяет тип запроса:

**Мероприятия из афиши** — если в запросе концерты, спектакли, выставки, джаз, фестивали и т.п.:

```text
джазовый концерт в эти выходные
стендап в субботу
```

**Места и заведения** — бильярд, боулинг, пляжи, бани, караоке, аквапарки и др.:

```text
куда сходить на бильярд
где в Москве обустроили пляжи
```

Для мест бот использует знания LLM и даёт ссылки на Яндекс.Карты. Перед визитом уточняйте адрес и часы работы на месте.

**Общие запросы:**

```text
чем заняться на выходных
найди в москве чем заняться на этих выходных
```

---

## Источники данных

| Источник | Slug | Тип | Статус |
|----------|------|-----|--------|
| [KudaGo API](https://kudago.com/public-api/v1.4/) | `kudago` | REST API | ✅ Универсальный (15 городов) |
| [Яндекс Афиша](https://afisha.yandex.ru) | `yandex_afisha` | HTML scraping | ⚠️ Универсальный (15 городов), возможны captcha |
| [Timepad](https://afisha.timepad.ru/) | `timepad` | HTML + JSON-LD | ✅ Универсальный (15 городов) |
| [MTS Live](https://live.mts.ru/) | `mts_live` | HTML + JSON-LD | ✅ Универсальный (15 городов) |
| [T-Bank Город](https://www.tbank.ru/gorod/afisha/) | `tbank_gorod` | HTML + JSON-LD | ✅ Универсальный (15 городов) |
| [Культура Москвы](https://www.mos.ru/kultura/) | `mos_kultura` | HTML scraping | ℹ️ Только Москва |
| [Time Out Москва](https://www.timeout.ru/msk) | `timeout_msk` | HTML scraping | ℹ️ Только Москва |
| [Мой спортивный район](https://moysportrayon.sport.mos.ru) | `mos_sport_rayon` | HTML scraping | ℹ️ Только Москва |
| [МТПП](https://mostpp.ru/events/) | `mtpp` | HTML + JSON-LD | ℹ️ Только Москва |

Синхронизация запускается:

- вручную: `python scripts/sync_events.py`
- автоматически: каждый день в **03:00** (APScheduler в `src/bot/main.py`)

Проверки покрытия:

- Москва (SC-002): `python scripts/count_events.py --city moscow --min-events 200 --min-sources 5`
- Все города: `python scripts/count_events.py --all-cities --min-events 30 --min-sources 2`

### Поддерживаемые города

Москва, Санкт-Петербург, Новосибирск, Екатеринбург, Казань, Нижний Новгород, Челябинск, Самара, Омск, Ростов-на-Дону, Уфа, Красноярск, Воронеж, Пермь, Волгоград.

### Категории событий

`concerts` · `exhibitions` · `theater` · `sport` · `education` · `other`

---

## Архитектура

```text
src/
├── bot/                 # Telegram: handlers, клавиатуры, форматирование
│   ├── handlers/        # start, categories, search, event_detail, settings
│   ├── formatters/      # HTML-сообщения для списков, карточек, мест
│   └── main.py          # Точка входа, polling, scheduler
├── ai/                  # LLM: ранжирование событий, подбор мест, intent
├── scrapers/            # KudaGo, Yandex Afisha, runner
└── storage/             # SQLAlchemy models, repositories, migrations (init/seed)

scripts/
└── sync_events.py       # CLI синхронизации

tests/
├── unit/                # ranker, formatters, dedup, filters
├── contract/            # схемы scraper/event
└── integration/         # onboarding, sync, settings
```

### Как работает ИИ

1. **Intent** (`src/ai/intent.py`) — запрос про место или про афишу.
2. **Places** (`src/ai/places.py`) — LLM подбирает заведения, форматтер добавляет карты.
3. **Ranker** (`src/ai/ranker.py`) — LLM выбирает `event_id` из кандидатов; при сбое — fuzzy fallback (rapidfuzz).
4. Кандидаты для афиши — до 100 событий города из БД, в LLM уходит компактная выборка (25 шт.).

---

## Тесты и качество кода

```bash
# Все тесты
pytest -q

# Только unit + contract (без сети)
pytest tests/unit tests/contract -v

# Линтер
ruff check src tests
```

CI (GitHub Actions): `.github/workflows/ci.yml` — ruff + pytest на каждый PR/push в `main`/`master`.

---

## Деплой и эксплуатация

### Локально (Windows / macOS / Linux)

- Терминал должен оставаться открытым, пока бот работает.
- Если Telegram API недоступен (частая ситуация в РФ без VPN) — включите **полный TUN-тunnel** или задайте `TELEGRAM_PROXY` (SOCKS5).

Проверка доступности:

```powershell
# Windows
Test-NetConnection api.telegram.org -Port 443
```

### VPS / Railway / Render (рекомендуется для 24/7)

1. Скопируйте репозиторий на сервер за рубежом.
2. Установите зависимости, настройте `.env`.
3. Выполните `init`, `seed`, `sync_events.py --all-cities`.
4. Запустите `python -m src.bot.main` через systemd, Docker или платформенный worker.
5. Для production БД используйте PostgreSQL:

   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/events
   ```

### PostgreSQL (Supabase)

Подключите `DATABASE_URL` с драйвером `asyncpg`, выполните `init` и `seed` на чистой базе.

---

## Устранение неполадок

| Проблема | Решение |
|----------|---------|
| `Cannot connect to host api.telegram.org` | VPN (TUN), прокси в `TELEGRAM_PROXY`, или деплой за рубежом |
| Бот не отвечает на `/start` | Проверьте `BOT_TOKEN`, один экземпляр polling, логи в терминале |
| Пустые категории | Запустите `python scripts/sync_events.py --city moscow` |
| `yandex_afisha saved=0` | Ожидаемо с многих IP; используйте KudaGo |
| ИИ: «Не удалось обработать запрос» | Проверьте `OPENAI_API_KEY`, лимиты Groq; fallback сработает для части запросов |
| `413 Payload Too Large` (Groq) | Уже mitigated в ranker (компактная выборка); обновите код до последней версии |
| Кнопка «Назад» не работает | Перезапустите бота после обновления handlers |

---

## Разработка

Спецификация и design-документы — в `specs/001-ai-event-discovery/`:

- `spec.md` — требования
- `plan.md` — архитектурный план
- `quickstart.md` — сценарии ручной проверки (V1–V6)
- `contracts/` — контракты API бота, scraper, event schema

Создание бота через BotFather, описание, аватар — настраиваются вручную в Telegram.

---

## Безопасность

- Храните `BOT_TOKEN` и `OPENAI_API_KEY` только в `.env` или secrets CI/CD.
- При утечке токена — перевыпустите в BotFather / у провайдера LLM.
- Рекомендации мест от ИИ не являются проверенной базой — это подсказки модели.

---

## Лицензия

Уточните лицензию в репозитории. При отсутствии файла `LICENSE` — all rights reserved автору проекта.
