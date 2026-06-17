from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.lists import add_button_row

from datetime import date

from src.bot.formatters.onboarding import city_label


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "🎲 Случайный вариант", "menu:random")
    add_button_row(builder, "📝 Опрос", "menu:survey")
    add_button_row(builder, "🔥 Популярное", "menu:popular")
    add_button_row(builder, "❤️ Избранное", "menu:favorites")
    add_button_row(builder, "📋 Подборки", "menu:collections")
    add_button_row(builder, "📅 Дата", "menu:date")
    add_button_row(builder, "⚙️ Настройки", "settings:open")
    return builder.as_markup()


def main_menu_text(city_slug: str, selected_date: date | None = None) -> str:
    date_text = selected_date.strftime("%d.%m.%Y") if selected_date else "не выбрана"
    return (
        f"Город: {city_label(city_slug)}\n"
        f"Дата поиска: {date_text}\n\n"
        "Выберите, как подобрать досуг:"
    )
