from src.bot.formatters.events import format_event_card, strip_html


def test_strip_html_removes_paragraph_tags() -> None:
    raw = "<p>Летом Roofevents открывает сезон</p><p>Второй абзац</p>"
    assert strip_html(raw) == "Летом Roofevents открывает сезон\nВторой абзац"


def test_format_event_card_has_no_raw_html() -> None:
    class Category:
        slug = "concerts"

    class Event:
        title = "Концерт"
        description = "<p>Описание <b>с HTML</b></p>"
        category = Category()
        venue = "Зал"
        start_at = __import__("datetime").datetime(2026, 6, 12, 13, 0, tzinfo=__import__("datetime").UTC)
        price_text = None
        price_type = "unknown"

    card = format_event_card(Event())  # type: ignore[arg-type]
    assert "<p>" not in card
    assert "Описание с HTML" in card
