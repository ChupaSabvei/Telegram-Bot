from __future__ import annotations

import re
from datetime import UTC, datetime
from html import unescape

from aiogram.enums import ParseMode

from src.bot.keyboards.menus import CATEGORY_LABELS, CITY_LABELS
from src.storage.models import Event

EVENT_MESSAGE_PARSE_MODE = ParseMode.HTML

CATEGORY_EMOJI = {
    "concerts": "🎵",
    "exhibitions": "🖼",
    "theater": "🎭",
    "sport": "⚽",
    "education": "📚",
    "other": "✨",
}

LIST_SEPARATOR = "───────────────"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def strip_html(text: str) -> str:
    cleaned = unescape(text)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</p>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<p[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _format_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%d.%m · %H:%M")


def _format_price(event: Event) -> str:
    if event.price_text:
        return event.price_text
    if event.price_type == "free":
        return "Бесплатно"
    return "Уточняйте на сайте"


def format_main_menu(city_slug: str) -> str:
    city_name = CITY_LABELS.get(city_slug, city_slug)
    return f"📍 Город: {city_name}\n\nВыберите категорию или напишите, что хотите посетить."


def format_event_list(events: list[Event], category_slug: str, city_slug: str) -> str:
    category_name = CATEGORY_LABELS.get(category_slug, category_slug)
    city_name = CITY_LABELS.get(city_slug, city_slug)
    emoji = CATEGORY_EMOJI.get(category_slug, "🎭")

    if not events:
        return (
            f"{emoji} <b>{_escape_html(category_name)}</b> · {_escape_html(city_name)}\n\n"
            f"Пока нет мероприятий на ближайший месяц.\n"
            "Попробуйте другую категорию."
        )

    shown = events[:20]
    lines = [
        f"{emoji} <b>{_escape_html(category_name)}</b> · {_escape_html(city_name)}",
        f"<i>{len(shown)} мероприятий — выберите номер ниже</i>",
        "",
    ]

    for idx, item in enumerate(shown, start=1):
        if idx > 1:
            lines.append(LIST_SEPARATOR)
        venue = _escape_html(item.venue or "Место уточняется")
        title = _escape_html(item.title)
        lines.extend(
            [
                f"<b>{idx}.</b> {title}",
                f"   📅 {_format_date(item.start_at)}",
                f"   📍 {venue}",
            ]
        )

    return "\n".join(lines)


def format_event_card(event: Event, stale_sync_text: str | None = None) -> str:
    category_slug = event.category.slug if event.category else "other"
    category_name = CATEGORY_LABELS.get(category_slug, "Категория")
    emoji = CATEGORY_EMOJI.get(category_slug, "📌")

    desc = strip_html(event.description or "Описание отсутствует")
    if len(desc) > 320:
        desc = f"{desc[:317]}..."

    lines = [
        f"{emoji} <b>{_escape_html(event.title)}</b>",
        "",
        f"📅 <b>Когда:</b> {_format_date(event.start_at)}",
        f"📍 <b>Где:</b> {_escape_html(event.venue or 'Место уточняется')}",
        f"💰 <b>Цена:</b> {_escape_html(_format_price(event))}",
        f"🏷 <b>Категория:</b> {_escape_html(category_name)}",
        "",
        LIST_SEPARATOR,
        "",
        f"<i>{_escape_html(desc)}</i>",
        "",
        "<i>👇 Подробности и билеты — по кнопке ниже</i>",
    ]
    if stale_sync_text:
        lines.extend(["", _escape_html(stale_sync_text)])
    return "\n".join(lines)


def stale_data_notice(sync_date: datetime) -> str:
    return (
        f"ℹ️ Данные обновлены {sync_date.strftime('%d.%m.%Y %H:%M')}. "
        "Некоторые источники временно недоступны."
    )
