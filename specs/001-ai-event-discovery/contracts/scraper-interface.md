# Scraper Interface Contract

**Version**: v1 | **Date**: 2026-06-12

## Protocol

Каждый скрапер в `src/scrapers/` MUST реализовать:

```python
class ScraperProtocol(Protocol):
    slug: str                    # "yandex_afisha" | "kudago"
    name: str                    # Human-readable name

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        """Fetch and normalize events for one city. Never raises to caller."""
```

## Output Contract

- Каждый элемент MUST валидироваться по `event-schema.json`
- `is_online` MUST быть `false`; иначе событие отбрасывается
- `start_at` MUST попадать в окно `[now, now + 30 days]` или отбрасывается
- Пустой список — допустимый результат (не ошибка)

## Error Handling

- Сетевые/парсинг ошибки: логировать, вернуть `[]`, установить
  `EventSource.last_sync_status = error`
- Частичный парсинг: вернуть валидные события, `last_sync_status = partial`

## Rate Limiting

| Source | Limit | Notes |
|--------|-------|-------|
| yandex_afisha | 1 req/s | Respect robots.txt |
| kudago | 3 req/s | Public API guidelines |

## Runner Contract (`src/scrapers/runner.py`)

```python
async def sync_all_sources(city_slugs: list[str] | None = None) -> SyncReport:
    """
    For each active source × city:
      1. fetch_events()
      2. validate against event-schema.json
      3. filter offline + date window
      4. deduplicate (see data-model.md)
      5. upsert to DB
    Returns: {source_slug, city_slug, fetched, saved, errors[]}
    """
```

## Registered Scrapers (MVP)

| slug | Module | Method |
|------|--------|--------|
| `yandex_afisha` | `yandex_afisha.py` | HTML scraping |
| `kudago` | `kudago.py` | REST API |

## Test Contract

`tests/contract/test_scraper_output.py` MUST:
- Загружать HTML/API fixtures из `tests/fixtures/`
- Проверять, что каждый скрапер возвращает валидный `EventDTO[]`
- Не делать live HTTP в CI (mock httpx)
