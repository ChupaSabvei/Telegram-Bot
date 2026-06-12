# AI Assistant Contract

**Version**: v1 | **Date**: 2026-06-12

## Module: `src/ai/ranker.py`

### Input

```python
@dataclass
class RankRequest:
    query: str              # User text, max 500 chars
    city_slug: str
    candidates: list[EventCandidate]  # Pre-filtered from DB, max 100

@dataclass
class EventCandidate:
    id: UUID
    title: str
    description: str | None
    category_slug: str
    start_at: datetime
    venue: str | None
    price_text: str | None
```

### Output

```python
@dataclass
class RankResponse:
    event_ids: list[UUID]           # Ordered by relevance, max 10
    clarification_needed: bool
    clarification_message: str | None
    prompt_version: str             # e.g. "v1"
    fallback_used: bool             # True if LLM unavailable
```

### Behavior Rules

1. **Happy path**: LLM получает JSON-кандидатов + запрос → возвращает
   `event_ids` (subset of candidate IDs, max 10)
2. **Unclear query**: `clarification_needed=true`, `event_ids=[]`,
   `clarification_message` на русском с предложением уточнить
3. **LLM failure** (timeout, 5xx, rate limit): `fallback_used=true`,
   keyword match по `title`/`description` + category hints; если пусто —
   `clarification_needed=true` с предложением выбрать категорию (FR-007)
4. **Latency budget**: 8 с на LLM-вызов (оставляет 2 с на DB + Telegram)

### Prompt Versioning

- Промпты в `src/ai/prompts.py` с константой `PROMPT_VERSION`
- Логировать: `prompt_version`, `candidate_count`, `latency_ms`, `fallback_used`
- Без логирования полного user query в проде (только hash или truncate 50 chars)

### LLM Response Schema (structured output)

```json
{
  "event_ids": ["uuid-1", "uuid-2"],
  "clarification_needed": false,
  "clarification_message": null
}
```

### Test Contract

`tests/unit/test_ai_ranker.py` MUST cover:
- Релевантный запрос → non-empty `event_ids`
- Неясный запрос → `clarification_needed=true`
- Mock LLM failure → `fallback_used=true`, non-error response
