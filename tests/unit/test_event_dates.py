from __future__ import annotations

from datetime import UTC, datetime

from src.scrapers.event_dates import MSK, parse_event_date_from_text


def test_parse_event_date_range_with_shared_month() -> None:
    parsed = parse_event_date_from_text(
        "Фестиваль «Вкус лета». Когда: 25 - 26 июля, начало в 12:00",
        now=datetime(2026, 6, 15, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.astimezone(MSK) == datetime(2026, 7, 25, 12, 0, tzinfo=MSK)


def test_parse_event_date_with_slashes_uses_nearby_time() -> None:
    parsed = parse_event_date_from_text(
        "МЕРОПРИЯТИЯ НЕДЕЛИ Среда // 17 июня // 19:00 Литературный клуб",
        now=datetime(2026, 6, 15, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.astimezone(MSK) == datetime(2026, 6, 17, 19, 0, tzinfo=MSK)


def test_parse_event_date_ignores_working_hours_before_date() -> None:
    parsed = parse_event_date_from_text(
        "Самый большой скалодром в Москве ⏰ Пн-Вс 10:00-23:00. Старт занятия 20 июня в 18:30",
        now=datetime(2026, 6, 15, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.astimezone(MSK) == datetime(2026, 6, 20, 18, 30, tzinfo=MSK)


def test_parse_event_date_with_calendar_emoji() -> None:
    parsed = parse_event_date_from_text(
        "Берём зонтики и отправляемся на фестиваль воздушных змеев 📆 14 июля, 15:00",
        now=datetime(2026, 6, 15, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.astimezone(MSK) == datetime(2026, 7, 14, 15, 0, tzinfo=MSK)


def test_parse_event_date_this_weekend() -> None:
    parsed = parse_event_date_from_text(
        "В эти выходные на ВДНХ пройдет фестиваль воздушной гимнастики",
        now=datetime(2026, 6, 15, 9, 0, tzinfo=UTC),
    )

    assert parsed is not None
    assert parsed.astimezone(MSK).date().isoformat() == "2026-06-20"
