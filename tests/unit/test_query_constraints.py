from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from src.ai.query_constraints import parse_query_constraints

MSK = timezone(timedelta(hours=3))


def test_parse_weekday_constraint_for_tuesday() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=MSK).astimezone(UTC)
    constraints = parse_query_constraints("Найди мне мероприятия во вторник", now=now)
    assert date(2026, 6, 16) in constraints.target_dates
    assert constraints.requires_confirmed_date is True


def test_parse_explicit_date_constraint() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=MSK).astimezone(UTC)
    constraints = parse_query_constraints("концерты 20.06", now=now)
    assert date(2026, 6, 20) in constraints.target_dates


def test_parse_weekday_constraint_for_friday_accusative() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=MSK).astimezone(UTC)
    constraints = parse_query_constraints("Найди мероприятия на пятницу", now=now)
    assert date(2026, 6, 19) in constraints.target_dates
    assert date(2026, 6, 15) not in constraints.target_dates


def test_parse_weekend_query_uses_nearest_saturday_sunday() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=MSK).astimezone(UTC)
    constraints = parse_query_constraints("Мероприятия на выходные", now=now)
    assert date(2026, 6, 20) in constraints.target_dates
    assert date(2026, 6, 21) in constraints.target_dates
    assert date(2026, 6, 26) not in constraints.target_dates


def test_upcoming_weekend_dates_on_monday() -> None:
    from src.ai.query_constraints import upcoming_weekend_dates

    now = datetime(2026, 6, 15, 12, 0, tzinfo=MSK).astimezone(UTC)
    weekend = upcoming_weekend_dates(now=now)
    assert weekend == frozenset({date(2026, 6, 20), date(2026, 6, 21)})


def test_parse_explicit_date_rolls_to_next_year_when_day_passed() -> None:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=MSK).astimezone(UTC)
    constraints = parse_query_constraints("концерты 1 января", now=now)
    assert date(2027, 1, 1) in constraints.target_dates
