from __future__ import annotations

from datetime import UTC, datetime

from src.bot.keyboards.menus import CATEGORY_LABELS, CITY_LABELS
from src.storage.models import Event


def format_main_menu(city_slug: str) -> str:
    city_name = CITY_LABELS.get(city_slug, city_slug)
    return f"📍 Город: {city_name}\n\nВыберите категорию или напишите, что хотите посетить."


def _format_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%d.%m %H:%M UTC")


def format_event_list(events: list[Event], category_slug: str, city_slug: str) -> str:
    category_name = CATEGORY_LABELS.get(category_slug, category_slug)
    city_name = CITY_LABELS.get(city_slug, city_slug)
    if not events:
        return (
            f"В категории «{category_name}» пока нет мероприятий на ближайший месяц.\n"
            "Попробуйте другую категорию."
        )
    lines = [f"🎭 {category_name} в {city_name}:", ""]
    for idx, item in enumerate(events[:10], start=1):
        venue = item.venue or "Место уточняется"
        lines.append(f"{idx}. {item.title} — {_format_date(item.start_at)}, {venue}")
    return "\n".join(lines)


def format_event_card(event: Event, stale_sync_text: str | None = None) -> str:
    category_name = CATEGORY_LABELS.get(event.category.slug if event.category else "", "Категория")
    desc = (event.description or "Описание отсутствует").strip()
    if len(desc) > 300:
        desc = f"{desc[:297]}..."
    lines = [
        f"📌 {event.title}",
        "",
        f"📅 {_format_date(event.start_at)}",
        f"📍 {event.venue or 'Место уточняется'}",
        f"💰 {event.price_text or 'уточняйте на сайте'}",
        f"🏷 {category_name}",
        "",
        desc,
        "",
        "🔗 Подробнее на сайте",
    ]
    if stale_sync_text:
        lines.extend(["", stale_sync_text])
    return "\n".join(lines)


def stale_data_notice(sync_date: datetime) -> str:
    return f"ℹ️ Данные обновлены {sync_date.strftime('%d.%m.%Y %H:%M')}. Некоторые источники временно недоступны."
