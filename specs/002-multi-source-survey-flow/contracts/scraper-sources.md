# Scraper Sources Contract (002)

**Version**: v2 | **Date**: 2026-06-14

Extends [001 scraper-interface](../001-ai-event-discovery/contracts/scraper-interface.md).

## ScraperProtocol (unchanged signature)

```python
async def fetch_events(self, city_slug: str) -> list[EventDTO]:
    """Never raise; return [] on failure."""
```

## Registered Sources

| Priority | slug | Module | city_slug scope | MVP target events |
|----------|------|--------|-----------------|-------------------|
| P0 | `kudago` | `kudago.py` | all 15 cities | existing |
| P0 | `yandex_afisha` | `yandex_afisha.py` | all 15 cities | best-effort |
| P1 | `timepad` | `timepad.py` | moscow | ≥ 30 |
| P1 | `mts_live` | `mts_live.py` | moscow | ≥ 30 |
| P1 | `mos_sport_rayon` | `mos_sport_rayon.py` | moscow | ≥ 20 |
| P2 | `tbank_gorod` | `tbank_gorod.py` | moscow | ≥ 20 |
| P2 | `timeout_msk` | `timeout_msk.py` | moscow | ≥ 15 |
| P2 | `mos_kultura` | `mos_kultura.py` | moscow | ≥ 15 |
| P3 | `mtpp` | `mtpp.py` | moscow | ≥ 10 |

**SC-002 gate**: Moscow sync must yield ≥ 200 unique events in 30-day window from ≥ 5 sources.

## Runner Behavior

1. For each scraper where `city_slug` in scraper.supported_cities (default `["moscow"]` for new scrapers):
   - Call `fetch_events(city_slug)`
   - Update `EventSource.last_sync_at`, `last_sync_status`, `last_error`
2. Classify per FR-021/023: (a) source fields; (b) `classifiers/activity.py` rule-based; (c) `ai/activity_classifier.py` if still null; (d) save unclassified if AI unavailable — retry next sync. Also set `venue_format`, `price_amount_rub`, compute `popularity_score`.
3. Upsert + dedup (001 logic + fuzzy)
4. Log per-source counts: `{slug}: fetched=N, saved=M, errors=0|1`

## Rate Limits

| Source | Delay | User-Agent |
|--------|-------|------------|
| Default | 1.0 s between requests | `TelegramEventBot/1.0 (+contact)` |
| mos.ru | 1.5 s | same |
| yandex_afisha | 2.0 s | same |

## Failure Isolation

- Scraper exception → `last_sync_status=error`, continue next scraper
- Captcha/403 → mark source `is_active=false` for 24h (configurable), log warning
- Bot MUST NOT crash on sync failure

## Fixtures (tests)

```text
tests/fixtures/html/
├── timepad_list.html
├── mts_live_moscow.html
├── mos_sport_rayon.html
├── tbank_gorod_list.html
├── timeout_msk_list.html
├── mos_kultura_list.html
└── mtpp_events.html
```

Each scraper MUST have ≥ 1 unit test parsing fixture without network.

## EventDTO v2

Output MUST validate against [event-schema-v2.json](./event-schema-v2.json).
