from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))

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
DATE_TEXT_RANGE = re.compile(
    r"\b(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+((?:" + "|".join(MONTH_BY_NAME) + r")[а-я]*)\b(?:\s+(\d{4}))?",
    re.IGNORECASE,
)
TIME_PATTERN = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
FROM_DAY_TEXT = re.compile(
    r"(?:\b(\d{4})\s*,\s*)?(?:[а-яA-Za-z]+\s+)?(?:с|со)\s+(\d{1,2})\s+((?:"
    + "|".join(MONTH_BY_NAME)
    + r")[а-я]*)",
    re.IGNORECASE,
)


def _coerce_year(year: int, *, reference: datetime) -> int:
    if year < 100:
        return 2000 + year
    return year


def selected_date_range_utc(selected_date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(selected_date, datetime.min.time(), tzinfo=MSK)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def _attach_time(day: datetime, text: str) -> datetime:
    compact = text.replace("//", " ").replace("—", "-").replace("–", "-")
    match = TIME_PATTERN.search(compact)
    if match is None:
        return day
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return day
    local = day.astimezone(MSK).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(UTC)


def _candidate_context(text: str, start: int, end: int) -> str:
    # Prefer time near the matched date. This avoids using opening hours from the
    # beginning of a post as the event start time.
    return text[max(0, start - 16) : min(len(text), end + 48)]


def _this_weekend(now: datetime) -> datetime:
    today = now.astimezone(MSK).date()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and now.astimezone(MSK).hour >= 23:
        days_until_saturday = 7
    saturday = today + timedelta(days=days_until_saturday)
    return datetime(saturday.year, saturday.month, saturday.day, tzinfo=MSK).astimezone(UTC)


def parse_utc_iso(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_msk_iso(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt.astimezone(UTC)


def combine_date_and_time(date_text: str, time_text: str, *, now: datetime | None = None) -> datetime | None:
    raw = date_text.strip()
    day = None
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        day = parse_msk_iso(raw[:10])
    if day is None:
        day = parse_msk_iso(raw)
    if day is None:
        day = parse_event_date_from_text(date_text, now=now)
    if day is None:
        return None
    time_match = TIME_PATTERN.search(time_text)
    if time_match is None:
        return day
    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    if hour > 23 or minute > 59:
        return day
    local = day.astimezone(MSK).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(UTC)


def pick_next_session(sessions: list[datetime], *, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(tz=UTC)
    future = sorted({coerce_utc(item) for item in sessions if coerce_utc(item) > now})
    return future[0] if future else None


def pick_session_for_date(sessions: list[datetime], selected_date: date) -> datetime | None:
    day_start, day_end = selected_date_range_utc(selected_date)
    on_day = sorted(
        {
            coerce_utc(item)
            for item in sessions
            if day_start <= coerce_utc(item) < day_end
        }
    )
    return on_day[0] if on_day else None


def coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def extract_iso_datetimes(
    data: object,
    *,
    parser=parse_msk_iso,
) -> list[datetime]:
    keys = frozenset(
        {
            "eventClosestDateTime",
            "lastEventDateTime",
            "eventContext",
            "dateTime",
            "startDateTime",
            "startAt",
        }
    )
    found: list[datetime] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and (key in keys or key.endswith("DateTime")):
                    parsed = parser(value)
                    if parsed is not None:
                        found.append(parsed)
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return sorted(set(found))


def parse_event_date_from_text(text: str, *, now: datetime | None = None) -> datetime | None:
    """Extract an event date/time from free-form Russian post text."""
    if not text.strip():
        return None
    now = now or datetime.now(tz=UTC)
    today = now.astimezone(MSK).date()
    candidates: list[datetime] = []

    for match in FROM_DAY_TEXT.finditer(text):
        year_raw = match.group(1)
        day = int(match.group(2))
        month_token = match.group(3).lower()
        month = next((num for prefix, num in MONTH_BY_NAME.items() if month_token.startswith(prefix)), None)
        if month is None:
            continue
        year = int(year_raw) if year_raw else today.year
        try:
            local = datetime(year, month, day, tzinfo=MSK)
        except ValueError:
            continue
        if year_raw is None and local.date() < today:
            try:
                local = datetime(year + 1, month, day, tzinfo=MSK)
            except ValueError:
                continue
        candidates.append(_attach_time(local.astimezone(UTC), _candidate_context(text, match.start(), match.end())))

    for match in DATE_TEXT_RANGE.finditer(text):
        day = int(match.group(1))
        month_token = match.group(3).lower()
        month = next((num for prefix, num in MONTH_BY_NAME.items() if month_token.startswith(prefix)), None)
        if month is None:
            continue
        year_raw = match.group(4)
        year = int(year_raw) if year_raw else today.year
        try:
            local = datetime(year, month, day, tzinfo=MSK)
        except ValueError:
            continue
        if year_raw is None and local.date() < today:
            try:
                local = datetime(year + 1, month, day, tzinfo=MSK)
            except ValueError:
                continue
        candidates.append(_attach_time(local.astimezone(UTC), _candidate_context(text, match.start(), match.end())))

    for match in DATE_NUMERIC.finditer(text):
        day = int(match.group(1))
        month = int(match.group(2))
        year_raw = match.group(3)
        year = _coerce_year(int(year_raw), reference=now) if year_raw else today.year
        try:
            local = datetime(year, month, day, tzinfo=MSK)
        except ValueError:
            continue
        if year_raw is None and local.date() < today:
            try:
                local = datetime(year + 1, month, day, tzinfo=MSK)
            except ValueError:
                continue
        candidates.append(_attach_time(local.astimezone(UTC), _candidate_context(text, match.start(), match.end())))

    for match in DATE_TEXT.finditer(text):
        day = int(match.group(1))
        month_token = match.group(2).lower()
        month = next((num for prefix, num in MONTH_BY_NAME.items() if month_token.startswith(prefix)), None)
        if month is None:
            continue
        year_raw = match.group(3)
        year = int(year_raw) if year_raw else today.year
        try:
            local = datetime(year, month, day, tzinfo=MSK)
        except ValueError:
            continue
        if year_raw is None and local.date() < today:
            try:
                local = datetime(year + 1, month, day, tzinfo=MSK)
            except ValueError:
                continue
        candidates.append(_attach_time(local.astimezone(UTC), _candidate_context(text, match.start(), match.end())))

    if not candidates:
        lowered = text.lower()
        if "эти выходн" in lowered or "выходные" in lowered:
            candidates.append(_this_weekend(now))
        else:
            return None

    horizon = now + timedelta(days=180)
    valid = [item for item in candidates if now - timedelta(days=1) <= item <= horizon]
    if not valid:
        return None
    return min(valid, key=lambda item: abs((item - now).total_seconds()))
