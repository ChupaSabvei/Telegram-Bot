<!--
Sync Impact Report
- Version change: template (unversioned) → 1.0.0
- Modified principles: all placeholders replaced with project-specific principles
  - [PRINCIPLE_1] → I. Modular Architecture
  - [PRINCIPLE_2] → II. AI-Assisted Event Discovery
  - [PRINCIPLE_3] → III. Reliable External Data Ingestion
  - [PRINCIPLE_4] → IV. Test-First Development (NON-NEGOTIABLE)
  - [PRINCIPLE_5] → V. Team-First GitHub Workflow
- Added sections: Technology Stack & Security Constraints; Development Workflow & Quality Gates
- Removed sections: none (template placeholders filled)
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (Constitution Check gates)
  - ✅ .cursor/rules/specify-rules.mdc (project context)
  - ⚠ .specify/templates/spec-template.md (no changes required — generic)
  - ⚠ .specify/templates/tasks-template.md (no changes required — paths set per plan)
- Follow-up TODOs: none
-->

# Telegram Event Bot Constitution

## Core Principles

### I. Modular Architecture

Кодовая база MUST быть разделена на независимые модули с чёткими границами
ответственности:

- `src/bot/` — Telegram-интерфейс, команды, диалоги, форматирование ответов
- `src/scrapers/` — сбор и нормализация мероприятий с внешних сайтов
- `src/ai/` — ИИ-помощник: интерпретация запросов, подбор и ранжирование
- `src/storage/` — персистентность: события, категории, кэш, пользовательские
  предпочтения

Модули MUST иметь явные контракты (типы/схемы данных) и MUST NOT обращаться к
внутренним деталям других модулей напрямую. Общая логика выносится в
переиспользуемые компоненты только при доказанной необходимости (YAGNI).

### II. AI-Assisted Event Discovery

ИИ-помощник MUST помогать пользователю находить мероприятия по категориям и
естественным запросам. Система MUST:

- Принимать текстовые запросы и выбирать релевантные категории
- Ранжировать результаты по соответствию запросу, дате и доступности
- Возвращать понятные ответы в Telegram (название, дата, место, ссылка)
- Деградировать gracefully при недоступности ИИ (fallback на фильтры по
  категориям без генерации)

Промпты и ответы ИИ MUST быть версионируемы и тестируемы; «магические»
непрозрачные цепочки без логирования запрещены.

### III. Reliable External Data Ingestion

Мероприятия MUST поступать из внешних интернет-источников через модуль
`src/scrapers/`. Каждый скрапер MUST:

- Приводить данные к единой схеме события (название, категория, дата, место,
  URL, источник)
- Обрабатывать ошибки сети и изменения вёрстки без падения бота
- Соблюдать rate limits и robots.txt там, где применимо
- Дедуплицировать события по URL или стабильному идентификатору

Сырые данные и кэш MUST NOT попадать в git; секреты и токены — только через
переменные окружения.

### IV. Test-First Development (NON-NEGOTIABLE)

Для критических путей (скраперы, схемы данных, ИИ-ранжирование, хендлеры бота)
применяется TDD:

1. Написать тест → получить одобрение → убедиться, что тест падает
2. Реализовать минимальный код → тест проходит
3. Рефакторинг без изменения поведения

Интеграционные тесты MUST покрывать: контракты между модулями, парсинг
реальных/фикстурных HTML-страниц, сценарии диалога бота. PR без тестов на новую
бизнес-логику MUST быть отклонён.

### V. Team-First GitHub Workflow

Разработка MUST вестись командой через GitHub:

- Каждая фича — отдельная ветка `###-feature-name` от `master`
- Изменения вливаются только через Pull Request с описанием и test plan
- Минимум один review перед merge (кроме срочных hotfix с пост-ревью)
- Мелкие атомарные коммиты с понятными сообщениями
- CI MUST проходить до merge (lint + tests)

Прямой push в `master` запрещён для командной работы.

## Technology Stack & Security Constraints

**Язык**: Python 3.11+

**Основные компоненты**:

- Telegram Bot API (python-telegram-bot или aiogram)
- ИИ-провайдер (OpenAI-совместимый API или аналог)
- HTTP-клиент и парсинг (httpx + BeautifulSoup; Playwright — при необходимости
  JS-рендеринга)
- Хранилище: PostgreSQL / Supabase или SQLite для локальной разработки

**Безопасность**:

- Токены бота, API-ключи ИИ и БД — только в `.env` (файл в `.gitignore`)
- `.env.example` MUST содержать шаблон без секретов
- Логи MUST NOT содержать персональные данные и секреты
- Зависимости фиксируются в `requirements.txt` или `pyproject.toml`

**Производительность**:

- Ответ бота пользователю — целевой p95 < 5 с для подбора мероприятий
- Скраперы работают асинхронно/по расписанию, не блокируя основной event loop

## Development Workflow & Quality Gates

1. **Specify** → уточнить требования в `specs/###-feature/spec.md`
2. **Plan** → технический план с Constitution Check в `plan.md`
3. **Tasks** → декомпозиция в `tasks.md`
4. **Implement** → код в feature-ветке, PR на GitHub
5. **Review** → проверка соответствия конституции, тестов и test plan

**Quality gates перед merge**:

- [ ] Constitution Check пройден (см. plan.md)
- [ ] Тесты зелёные
- [ ] Нет секретов в diff
- [ ] Документация/quickstart обновлены при изменении API или деплоя

Структура репозитория:

```text
src/
├── bot/
├── scrapers/
├── ai/
└── storage/
tests/
├── unit/
├── integration/
└── contract/
specs/
└── ###-feature-name/
```

## Governance

Эта конституция имеет приоритет над неформальными договорённостями и ad-hoc
решениями. Любое изменение принципов или ограничений MUST:

1. Оформляться через PR с обновлением `.specify/memory/constitution.md`
2. Сопровождаться bump версии по semver (см. ниже)
3. Синхронизировать зависимые шаблоны в `.specify/templates/` и
   `.cursor/rules/`

**Версионирование конституции**:

- MAJOR — удаление или переопределение принципа
- MINOR — новый принцип или существенное расширение раздела
- PATCH — уточнения формулировок без изменения смысла

Все PR и code review MUST проверять соответствие конституции. Сложность сверх
минимально достаточной MUST быть обоснована в `plan.md` (Complexity Tracking).
Оперативные инструкции для агентов и разработчиков — в
`.cursor/rules/specify-rules.mdc` и `specs/`.

**Version**: 1.0.0 | **Ratified**: 2026-06-12 | **Last Amended**: 2026-06-12
