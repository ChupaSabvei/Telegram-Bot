from __future__ import annotations

from html import unescape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.formatters.events import strip_html

TELEGRAM_BUTTON_TEXT_MAX = 64


def add_button_row(builder: InlineKeyboardBuilder, text: str, callback_data: str) -> None:
    builder.row(InlineKeyboardButton(text=text, callback_data=callback_data))


def back_button_row(builder: InlineKeyboardBuilder) -> None:
    add_button_row(builder, "⬅️ Назад", "nav:main")


def list_with_back_keyboard(
    buttons: list[tuple[str, str]],
    *,
    extra_rows: list[tuple[str, str]] | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for text, callback_data in buttons:
        add_button_row(builder, text, callback_data)
    if extra_rows:
        for text, callback_data in extra_rows:
            add_button_row(builder, text, callback_data)
    back_button_row(builder)
    return builder.as_markup()


def clean_button_label(text: str, *, prefix: str = "") -> str:
    cleaned = unescape(strip_html(text)).strip() or "Событие"
    max_len = TELEGRAM_BUTTON_TEXT_MAX - len(prefix)
    if len(cleaned) <= max_len:
        return f"{prefix}{cleaned}"
    return f"{prefix}{cleaned[: max_len - 1]}…"


def collection_index_button_label(title: str, *, events_count: int) -> str:
    prefix = "📋 "
    suffix = f" — {events_count} событ."
    max_title_len = TELEGRAM_BUTTON_TEXT_MAX - len(prefix) - len(suffix)
    cleaned = unescape(strip_html(title)).strip() or "Подборка"
    if len(cleaned) > max_title_len:
        cleaned = f"{cleaned[: max_title_len - 1]}…"
    return f"{prefix}{cleaned}{suffix}"
