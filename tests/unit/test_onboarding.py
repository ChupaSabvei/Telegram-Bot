from __future__ import annotations

from src.bot.formatters.onboarding import first_launch_guide, welcome_city_prompt


def test_welcome_city_prompt_mentions_city() -> None:
    text = welcome_city_prompt()
    assert "город" in text.lower()


def test_first_launch_guide_covers_standard_and_ai() -> None:
    text = first_launch_guide("moscow")
    assert "Стандартные сценарии" in text
    assert "ИИ-ассистент" in text
    assert "Москва" in text
    assert "опрос" in text.lower()
