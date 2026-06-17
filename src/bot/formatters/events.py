from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta, timezone
from html import unescape

from aiogram.enums import ParseMode

from src.bot.keyboards.menus import CATEGORY_LABELS, CITY_LABELS
from src.scrapers.event_dates import parse_event_date_from_text
from src.storage.event_times import display_time_confirmed, resolve_display_start
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
MSK = timezone(timedelta(hours=3))


def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


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


def _is_social_post(event: Event) -> bool:
    source_slug = getattr(getattr(event, "source", None), "slug", "")
    source_url = str(getattr(event, "source_url", "") or "")
    return (
        source_slug == "telegram_channels"
        or "t.me/" in source_url
        or "vk.ru/" in source_url
        or "vk.com/" in source_url
    )


def _format_date(event: Event, *, confirmed: bool = True, selected_date: date | None = None) -> str:
    if _is_social_post(event):
        if confirmed:
            display_start = resolve_display_start(event, selected_date)
            if display_start is None:
                return "дата уточняется"
            return _coerce_utc(display_start).astimezone(MSK).strftime("%d.%m · %H:%M")
        text = " ".join(filter(None, [strip_html(event.title), strip_html(event.description or "")]))
        parsed = parse_event_date_from_text(text)
        if parsed is None:
            return "дата уточняется"
        dt = parsed
    else:
        display_start = resolve_display_start(event, selected_date)
        if display_start is None or not display_time_confirmed(event, display_start):
            return "дата уточняется"
        dt = display_start
    return _coerce_utc(dt).astimezone(MSK).strftime("%d.%m · %H:%M")


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
                f"   📅 {_format_date(item, confirmed=getattr(item, 'start_at_confirmed', True))}",
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

    when = _format_date(event, confirmed=getattr(event, "start_at_confirmed", True))
    lines = [
        f"{emoji} <b>{_escape_html(event.title)}</b>",
        "",
        f"📅 <b>Когда:</b> {when}",
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
