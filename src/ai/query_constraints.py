from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))

WEEKDAY_BY_NAME: dict[str, int] = {
    "понедельник": 0,
    "понедельника": 0,
    "понедельнику": 0,
    "пн": 0,
    "вторник": 1,
    "вторника": 1,
    "вторнику": 1,
    "вт": 1,
    "среда": 2,
    "среды": 2,
    "среде": 2,
    "среду": 2,
    "ср": 2,
    "четверг": 3,
    "четверга": 3,
    "четвергу": 3,
    "чт": 3,
    "пятница": 4,
    "пятницы": 4,
    "пятнице": 4,
    "пятницу": 4,
    "пт": 4,
    "суббота": 5,
    "субботы": 5,
    "субботе": 5,
    "субботу": 5,
    "сб": 5,
    "воскресенье": 6,
    "воскресенья": 6,
    "воскресенью": 6,
    "воскресенье": 6,
    "вс": 6,
}

MONTH_BY_NAME: dict[str, int] = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}

DATE_NUMERIC = re.compile(
    r"\b(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\b",
)
DATE_TEXT = re.compile(
    r"\b(\d{1,2})\s+((?:" + "|".join(MONTH_BY_NAME) + r")[а-я]*)\b(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

WEEKEND_KEYWORDS = ("выходн", "weekend", "суббот", "воскресен")


@dataclass(slots=True, frozen=True)
class QueryConstraints:
    target_dates: frozenset[date]
    requires_confirmed_date: bool


def _today_msk(now: datetime) -> date:
    return now.astimezone(MSK).date()


def _next_weekday(from_day: date, weekday: int) -> date:
    days_ahead = (weekday - from_day.weekday()) % 7
    return from_day + timedelta(days=days_ahead)


def is_weekend_query(query: str) -> bool:
    lowered = query.lower()
    return any(keyword in lowered for keyword in WEEKEND_KEYWORDS)


def upcoming_weekend_dates(*, now: datetime | None = None) -> frozenset[date]:
    """Nearest weekend in MSK: Sat+Sun (Mon–Fri), today only on Sunday."""
    now = now or datetime.now(tz=UTC)
    today = now.astimezone(MSK).date()
    weekday = today.weekday()
    if weekday == 5:
        return frozenset({today, today + timedelta(days=1)})
    if weekday == 6:
        return frozenset({today})
    days_until_saturday = (5 - weekday) % 7
    saturday = today + timedelta(days=days_until_saturday)
    return frozenset({saturday, saturday + timedelta(days=1)})


def _extract_weekdays(query: str) -> set[int]:
    lowered = query.lower()
    found: set[int] = set()
    for name, weekday in WEEKDAY_BY_NAME.items():
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            found.add(weekday)
    return found


def _extract_explicit_dates(query: str, *, today: date) -> set[date]:
    found: set[date] = set()
    for match in DATE_NUMERIC.finditer(query):
        day = int(match.group(1))
        month = int(match.group(2))
        year_raw = match.group(3)
        year = int(year_raw) if year_raw else today.year
        if year_raw and len(year_raw) == 2:
            year = 2000 + year
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if year_raw is None and candidate < today:
            try:
                candidate = date(year + 1, month, day)
            except ValueError:
                continue
        found.add(candidate)

    for match in DATE_TEXT.finditer(query):
        day = int(match.group(1))
        month_token = match.group(2).lower()
        month = next((num for prefix, num in MONTH_BY_NAME.items() if month_token.startswith(prefix)), None)
        if month is None:
            continue
        year_raw = match.group(3)
        year = int(year_raw) if year_raw else today.year
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if year_raw is None and candidate < today:
            try:
                candidate = date(year + 1, month, day)
            except ValueError:
                continue
        found.add(candidate)
    return found


def parse_query_constraints(query: str, *, now: datetime | None = None) -> QueryConstraints:
    now = now or datetime.now(tz=UTC)
    today = _today_msk(now)
    target_dates: set[date] = _extract_explicit_dates(query, today=today)

    for weekday in _extract_weekdays(query):
        target_dates.add(_next_weekday(today, weekday))

    if is_weekend_query(query):
        target_dates.update(upcoming_weekend_dates(now=now))

    return QueryConstraints(
        target_dates=frozenset(target_dates),
        requires_confirmed_date=bool(target_dates),
    )


def event_matches_constraints(
    start_at: datetime,
    *,
    start_at_confirmed: bool,
    constraints: QueryConstraints,
) -> bool:
    if not constraints.target_dates:
        return True
    event_day = start_at.astimezone(MSK).date()
    if event_day not in constraints.target_dates:
        return False
    if constraints.requires_confirmed_date and not start_at_confirmed:
        return False
    return True
