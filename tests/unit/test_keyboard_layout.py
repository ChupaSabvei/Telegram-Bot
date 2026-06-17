from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.lists import (
    TELEGRAM_BUTTON_TEXT_MAX,
    add_button_row,
    collection_index_button_label,
    list_with_back_keyboard,
)


def test_collection_index_button_label_truncates_long_title() -> None:
    title = "Очень длинное название подборки которое не помещается в кнопку Telegram целиком"
    label = collection_index_button_label(title, events_count=3)

    assert len(label) <= TELEGRAM_BUTTON_TEXT_MAX
    assert label.startswith("📋 ")
    assert label.endswith(" — 3 событ.")
    assert "…" in label


def test_list_with_back_keyboard_one_button_per_row() -> None:
    markup = list_with_back_keyboard(
        [("Первое событие", "evt:1"), ("Второе событие", "evt:2")],
        extra_rows=[("📋 Подборки", "menu:collections")],
    )

    assert len(markup.inline_keyboard) == 4
    assert all(len(row) == 1 for row in markup.inline_keyboard)


def test_add_button_row_always_creates_single_button_row() -> None:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "✏️ Переименовать", "col:rename:1")
    add_button_row(builder, "✂️ Убрать события", "col:edit:1")

    markup = builder.as_markup()
    assert len(markup.inline_keyboard) == 2
    assert markup.inline_keyboard[0][0].text == "✏️ Переименовать"
    assert markup.inline_keyboard[1][0].text == "✂️ Убрать события"
