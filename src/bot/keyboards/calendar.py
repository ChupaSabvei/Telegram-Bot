from __future__ import annotations

from calendar import monthrange
from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

WEEKDAY_LABELS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def month_keyboard(month: date, selected_date: date | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prev_month = _shift_month(month, -1)
    next_month = _shift_month(month, 1)
    builder.row(
        *[
            _btn("◀️", f"date:month:{prev_month.isoformat()}"),
            _btn(month.strftime("%B %Y").capitalize(), "date:noop"),
            _btn("▶️", f"date:month:{next_month.isoformat()}"),
        ]
    )
    builder.row(*[_btn(label, "date:noop") for label in WEEKDAY_LABELS])

    first_weekday, days_count = monthrange(month.year, month.month)
    # monthrange uses Monday=0 which matches labels
    day = 1
    for week_idx in range(6):
        row = []
        for weekday_idx in range(7):
            slot = week_idx * 7 + weekday_idx
            if slot < first_weekday or day > days_count:
                row.append(_btn(" ", "date:noop"))
                continue
            current = date(month.year, month.month, day)
            label = f"[{day}]" if selected_date == current else str(day)
            row.append(_btn(label, f"date:pick:{current.isoformat()}"))
            day += 1
        builder.row(*row)
        if day > days_count:
            break

    builder.row(_btn("Сбросить дату", "date:clear"))
    builder.row(_btn("⬅️ Назад", "nav:main"))
    return builder.as_markup()


def _shift_month(current: date, shift: int) -> date:
    month = current.month + shift
    year = current.year
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _btn(text: str, callback_data: str):  # type: ignore[no-untyped-def]
    from aiogram.types import InlineKeyboardButton

    return InlineKeyboardButton(text=text, callback_data=callback_data)

