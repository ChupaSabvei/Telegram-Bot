from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.lists import add_button_row


def audience_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "👤 Один", "survey:aud:solo")
    add_button_row(builder, "👫 Пара", "survey:aud:couple")
    add_button_row(builder, "👨‍👩‍👧‍👦 Семья", "survey:aud:family")
    add_button_row(builder, "👥 Друзья", "survey:aud:friends")
    return builder.as_markup()


def activity_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "⚽️ Спорт", "survey:act:sport")
    add_button_row(builder, "🎠 Для детей", "survey:act:kids")
    add_button_row(builder, "🏕 Семейный отдых", "survey:act:family")
    add_button_row(builder, "🎨 Культура", "survey:act:culture")
    add_button_row(builder, "🍽 Гастро", "survey:act:gastro")
    add_button_row(builder, "🧘 Релакс", "survey:act:relax")
    return builder.as_markup()


def budget_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "🆓 Бесплатно", "survey:bud:free")
    add_button_row(builder, "💵 до 1000₽", "survey:bud:1000")
    add_button_row(builder, "💰 до 3000₽", "survey:bud:3000")
    add_button_row(builder, "💎 Без лимита", "survey:bud:unlimited")
    return builder.as_markup()


def result_keyboard(event_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "➡️ Другой вариант", "result:next")
    add_button_row(builder, "❤️ В избранное", f"result:fav:{event_id}")
    add_button_row(builder, "⬅️ Назад", "result:restart")
    return builder.as_markup()


def empty_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "Смягчить бюджет", "empty:budget")
    add_button_row(builder, "🔄 Заново", "empty:restart")
    return builder.as_markup()
