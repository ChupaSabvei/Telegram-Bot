from __future__ import annotations

from src.scrapers.telegram_channels import TelegramChannelsScraper


def test_telegram_source_normalization_from_url() -> None:
    platform, slug, url = TelegramChannelsScraper._normalize_source("https://t.me/TOT_STANDUP")
    assert platform == "telegram"
    assert slug == "TOT_STANDUP"
    assert url == "https://t.me/s/TOT_STANDUP"


def test_vk_source_normalization_from_url() -> None:
    platform, slug, url = TelegramChannelsScraper._normalize_source("https://vk.ru/timepadru")
    assert platform == "vk"
    assert slug == "timepadru"
    assert url == "https://vk.ru/timepadru"


def test_title_from_text_skips_noise_lines() -> None:
    raw = (
        "На Пушкинской набережной проходят бесплатные занятия йогой.\n"
        "Подпишитесь на нас в MAX: max.ru/channel\n"
        "По всем вопросам: @manager"
    )
    title = TelegramChannelsScraper._title_from_text(raw)
    cleaned = TelegramChannelsScraper._clean_text(raw)
    assert "Подпиш" not in title
    assert "MAX" not in title
    assert "йогой" in title
    assert "Подпиш" not in cleaned


def test_title_from_text_strips_photo_credit_and_max_inline() -> None:
    raw = (
        "Лесная библиотека, парк 50-летия Октября 📚 Фото: Дарья Корж "
        "Подпишитесь на нас в Max"
    )
    title = TelegramChannelsScraper._title_from_text(raw)
    cleaned = TelegramChannelsScraper._clean_text(raw)
    assert "Фото" not in title
    assert "Подпиш" not in title
    assert "Max" not in title
    assert "Лесная библиотека" in title
    assert "Фото" not in cleaned


def test_resolve_start_at_without_event_date_is_not_confirmed() -> None:
    text = "Лесная библиотека, парк 50-летия Октября"
    start_at, confirmed = TelegramChannelsScraper._resolve_start_at(text, text, None)
    assert confirmed is False
    assert start_at.tzinfo is not None


def test_resolve_start_at_with_event_date_is_confirmed() -> None:
    text = "Концерт 20.06 в 19:00 в парке Горького"
    start_at, confirmed = TelegramChannelsScraper._resolve_start_at(text, text, None)
    assert confirmed is True
    assert start_at.day == 20
    assert start_at.month == 6


def test_resolve_start_at_with_russian_month_is_confirmed() -> None:
    text = "Креативная тусовка. Когда: 18 июня 18:00 - 23:00"
    start_at, confirmed = TelegramChannelsScraper._resolve_start_at(text, text, None)
    assert confirmed is True
    assert start_at.day == 18
    assert start_at.month == 6

