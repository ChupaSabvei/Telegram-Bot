from __future__ import annotations

from src.bot.keyboards.menus import city_keyboard


def test_city_keyboard_can_include_back_button() -> None:
    keyboard = city_keyboard(include_back=True)
    buttons = [button for row in keyboard.inline_keyboard for button in row]

    assert any(button.text == "◀️ Назад" and button.callback_data == "settings:back" for button in buttons)
