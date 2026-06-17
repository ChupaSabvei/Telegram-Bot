from __future__ import annotations

from datetime import UTC, date, datetime

from src.scrapers.event_dates import MSK, parse_msk_iso, parse_utc_iso, pick_session_for_date, pick_next_session, selected_date_range_utc


def coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_session_iso(value: str | datetime) -> datetime | None:
    if isinstance(value, datetime):
        return coerce_utc(value)
    if not value or not str(value).strip():
        return None
    return parse_utc_iso(str(value).strip()) or parse_msk_iso(str(value).strip())


def all_session_times(event) -> list[datetime]:
    times: list[datetime] = []
    seen: set[datetime] = set()
    for candidate in (getattr(event, "start_at", None), *(getattr(event, "session_starts_at", None) or [])):
        if candidate is None:
            continue
        parsed = parse_session_iso(candidate) if not isinstance(candidate, datetime) else coerce_utc(candidate)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        times.append(parsed)
    return sorted(times)


def has_explicit_time(dt: datetime) -> bool:
    local = coerce_utc(dt).astimezone(MSK)
    return not (local.hour == 0 and local.minute == 0)


def event_in_date_range(event, start: datetime, end: datetime) -> bool:
    if not getattr(event, "start_at_confirmed", True):
        return False
    return any(start <= session < end for session in all_session_times(event))


def resolve_display_start(event, selected_date: date | None = None, *, now: datetime | None = None) -> datetime | None:
    sessions = all_session_times(event)
    if not sessions:
        return None
    if selected_date is not None:
        on_day = pick_session_for_date(sessions, selected_date)
        if on_day is not None:
            return on_day
    upcoming = pick_next_session(sessions, now=now)
    if upcoming is not None:
        return upcoming
    return sessions[0]


def event_on_any_of_dates(event, dates: set[date]) -> bool:
    for target in dates:
        start, end = selected_date_range_utc(target)
        if event_in_date_range(event, start, end):
            return True
    return False


def display_time_confirmed(event, display_start: datetime | None) -> bool:
    if display_start is None:
        return False
    if not getattr(event, "start_at_confirmed", True):
        return False
    return has_explicit_time(display_start)
