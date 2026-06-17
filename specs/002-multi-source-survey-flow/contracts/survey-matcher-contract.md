# Survey Matcher Contract

**Version**: v1 | **Date**: 2026-06-14

## Module

`src/bot/services/survey_matcher.py` (or `src/ai/survey_matcher.py`)

## Input

```python
@dataclass
class SurveyFilters:
    city_slug: str
    audience: Literal["solo", "couple", "family", "friends"]
    activity: Literal["sport", "kids", "family", "culture", "gastro", "relax"]
    budget: Literal["free", "1000", "3000", "unlimited"]
    format: Literal["indoor", "any", "home"]
    exclude_ids: list[UUID]
```

## Output

```python
@dataclass
class MatchResult:
    event: Event | None
    candidates_remaining: int
    relaxed: bool  # True if softening was applied internally (should stay False per FR-020)
```

## Rules (deterministic)

1. **Horizon**: `start_at` in (now, now+30d]
2. **Activity**: `activity_slug == filters.activity`
3. **Audience**: event.audience_tags empty OR intersects mapped audience (family → family|kids; solo → any)
4. **Budget**:
   - `free` → `price_type == free`
   - `1000`/`3000` → `price_type == free` OR `price_amount_rub <= N` OR `price_amount_rub IS NULL`
   - `unlimited` → no price filter
5. **Format**:
   - `indoor` → `venue_format in (indoor, mixed)`
   - `any` → no filter (exclude pure online unless mixed venue)
   - `home` → `venue_format == online` OR `is_online == true`
6. **Exclude**: `id not in exclude_ids`
7. **Order**: `popularity_score DESC`, then `start_at ASC`
8. **Limit**: 1 event per call

## Empty Result

Return `event=None`, `candidates_remaining=0`. Caller shows empty keyboard (FR-020).

## Softening (user-triggered only)

| Action | Filter change |
|--------|---------------|
| `empty:budget` | Upgrade budget one tier |
| `empty:format` | Set format=`any` |

Re-run matcher with same FSM except updated field.

## Fallback (no AI)

If zero candidates and user did not soften: do NOT call LLM. Optional: suggest «Популярное» via button.

## Tests (required)

- `test_matcher_family_outdoor_budget_3000`
- `test_matcher_home_online_only`
- `test_matcher_excludes_shown_ids`
- `test_matcher_empty_no_auto_relax`
