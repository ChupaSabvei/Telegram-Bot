from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.bot.formatters.events import format_event_card
from src.scrapers.event_dates import parse_event_date_from_text


def test_format_event_card_displays_moscow_time_for_regular_sources() -> None:
    event = MagicMock()
    event.source = MagicMock(slug="kudago")
    event.source_url = "https://kudago.com/event/123"
    event.title = "Концерт"
    event.description = "Описание"
    event.start_at = datetime(2026, 6, 18, 16, 0, tzinfo=UTC)  # 19:00 MSK
    event.start_at_confirmed = True
    event.venue = "Клуб"
    event.price_text = "1000 ₽"
    event.price_type = "paid"
    event.category = MagicMock(slug="concerts")

    text = format_event_card(event)
    assert "18.06 · 19:00" in text


def test_format_event_card_uses_confirmed_social_start_at_without_reparsing() -> None:
    event = MagicMock()
    event.source = MagicMock(slug="telegram_channels")
    event.source_url = "https://t.me/detstvo_msk/123"
    event.title = "Берём зонтики и отправляемся на фестиваль воздушных змеев"
    event.description = "📆 14 июня гостей ждут творческие мастерские."
    event.start_at = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)  # 12:00 MSK
    event.start_at_confirmed = True
    event.venue = "Telegram: @detstvo_msk"
    event.price_text = None
    event.price_type = "free"
    event.category = MagicMock(slug="sport")

    text = format_event_card(event)

    assert "14.06 · 12:00" in text
    assert "дата уточняется" not in text


def test_parse_event_date_from_text_handles_date_range_with_month_at_end() -> None:
    parsed = parse_event_date_from_text(
        "Фестиваль «Вкус лета». Когда: 25 - 26 июля, 12:30.",
        now=datetime(2026, 6, 15, 9, 0, tzinfo=UTC),
    )

    assert parsed == datetime(2026, 7, 25, 9, 30, tzinfo=UTC)


def test_parse_event_date_from_text_handles_slash_separated_date_and_time() -> None:
    parsed = parse_event_date_from_text(
        "Среда // 17 июня // 19:00 Литературный клуб.",
        now=datetime(2026, 6, 15, 9, 0, tzinfo=UTC),
    )

    assert parsed == datetime(2026, 6, 17, 16, 0, tzinfo=UTC)


def test_parse_event_date_from_text_handles_emoji_prefixed_date() -> None:
    parsed = parse_event_date_from_text(
        "📆 14 июня гостей ждут творческие мастерские.",
        now=datetime(2026, 6, 13, 9, 0, tzinfo=UTC),
    )

    assert parsed == datetime(2026, 6, 13, 21, 0, tzinfo=UTC)
