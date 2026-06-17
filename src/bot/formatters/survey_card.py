from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta, timezone
from urllib.parse import quote

from html import unescape

from src.bot.formatters.events import _escape_html, strip_html
from src.scrapers.event_dates import parse_event_date_from_text
from src.storage.event_times import display_time_confirmed, event_on_any_of_dates, resolve_display_start
from src.storage.models import Event

AUDIENCE_LABELS = {
    "solo": "одного",
    "couple": "пары",
    "family": "семьи",
    "friends": "компании друзей",
}

BUDGET_LABELS = {
    "free": "бесплатно",
    "1000": "до 1000₽",
    "3000": "до 3000₽",
    "unlimited": "без лимита",
}

MAX_HIGHLIGHT_LEN = 220


def _maps_url(event: Event) -> str:
    location = event.address or event.venue or event.title
    return f"https://yandex.ru/maps/?text={quote(location)}"


def _price_display(event: Event) -> str:
    if event.price_type == "free":
        return "Бесплатно"
    if event.price_text:
        return strip_html(event.price_text)
    if event.price_amount_rub is not None:
        return f"от {event.price_amount_rub} ₽"
    return "уточняйте на сайте"


def _truncate(text: str, limit: int = MAX_HIGHLIGHT_LEN) -> str:
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rsplit(" ", 1)[0]
    return f"{trimmed}…"


def _summary_lines(description: str | None, *, limit: int = 2) -> list[str]:
    if not description:
        return []
    plain = re.sub(r"\s+", " ", strip_html(description))
    if not plain:
        return []

    parts = re.split(r"(?<=[.!?…])\s+", plain)
    lines: list[str] = []
    for part in parts:
        cleaned = part.strip(" ,;—-")
        if len(cleaned) < 12:
            continue
        lines.append(_truncate(cleaned))
        if len(lines) >= limit:
            return lines

    if not lines and plain:
        lines.append(_truncate(plain))
    return lines


def _highlights(event: Event) -> list[str]:
    title_plain = strip_html(event.title).strip()
    lines = _summary_lines(event.description)
    lines = [line for line in lines if line.strip().lower() != title_plain.lower()]
    if not lines:
        lines.append(event.category.name_ru if event.category else "Мероприятие")
    return lines[:2]


def _post_link_line(event: Event) -> str:
    source_slug = getattr(getattr(event, "source", None), "slug", "")
    source_url = str(event.source_url)
    if source_slug == "telegram_channels" or "t.me/" in source_url or "vk.ru/" in source_url or "vk.com/" in source_url:
        return f'\n📣 <a href="{source_url}">Пост в источнике</a>'
    return ""


def _is_social_post(event: Event) -> bool:
    source_slug = getattr(getattr(event, "source", None), "slug", "")
    source_url = str(event.source_url)
    return (
        source_slug == "telegram_channels"
        or "t.me/" in source_url
        or "vk.ru/" in source_url
        or "vk.com/" in source_url
    )


def _format_event_datetime(event: Event, *, selected_date: date | None = None) -> str | None:
    msk = timezone(timedelta(hours=3))
    if _is_social_post(event):
        text = " ".join(filter(None, [strip_html(event.title), strip_html(event.description or "")]))
        parsed = parse_event_date_from_text(text)
        if parsed is None:
            return None
        start = _coerce_utc(parsed).astimezone(msk)
        return start.strftime("%d.%m.%Y %H:%M (МСК)")
    display_start = resolve_display_start(event, selected_date)
    if display_start is None or not display_time_confirmed(event, display_start):
        return None
    start = _coerce_utc(display_start).astimezone(msk)
    return start.strftime("%d.%m.%Y %H:%M (МСК)")


def format_survey_card(
    event: Event,
    *,
    audience: str,
    budget: str,
    selected_date: date | None = None,
) -> str:
    audience_label = AUDIENCE_LABELS.get(audience, audience)
    budget_label = BUDGET_LABELS.get(budget, budget)
    highlights = _highlights(event)
    highlight_lines = "\n".join(f"— {_escape_html(line)}" for line in highlights)
    location = _escape_html(strip_html(event.address or event.venue or "уточняйте на сайте"))
    maps_url = _maps_url(event)
    source_url = str(event.source_url)
    post_link_line = _post_link_line(event)
    event_dt = _format_event_datetime(event, selected_date=selected_date)
    date_line = f"📅 {event_dt}\n" if event_dt else ""
    header = f"🤖 Для {audience_label} с бюджетом {budget_label}:"
    return (
        f"{header}\n\n"
        f"🧩 {_escape_html(strip_html(event.title))}\n"
        f"{date_line}"
        f"{highlight_lines}\n"
        f"— Вход: {_escape_html(_price_display(event))}\n\n"
        f"📍 {location}\n"
        f'🔗 <a href="{source_url}">Подробнее</a> · <a href="{maps_url}">Навигатор</a>'
        f"{post_link_line}"
    )


def format_simple_card(event: Event, *, selected_date: date | None = None) -> str:
    full = format_survey_card(
        event,
        audience="solo",
        budget="unlimited",
        selected_date=selected_date,
    )
    if full.startswith("🤖 Для "):
        lines = full.splitlines()
        return "\n".join(lines[2:]) if len(lines) > 2 else full
    return full


def _display_text(text: str) -> str:
    return _escape_html(unescape(strip_html(text)))


def format_popular_list(
    events: list[Event],
    *,
    offset: int = 0,
    selected_date: date | None = None,
) -> str:
    if not events:
        return "Пока нет популярных событий в вашем городе."
    lines = ["🔥 Популярное на ближайшие 30 дней:\n"]
    for idx, event in enumerate(events, start=1 + offset):
        date_str = ""
        display_start = resolve_display_start(event, selected_date)
        if display_start is not None and display_time_confirmed(event, display_start):
            date_str = f" ({_coerce_utc(display_start).astimezone(timezone(timedelta(hours=3))).strftime('%d.%m')})"
        lines.append(f"{idx}. {_display_text(event.title)}{date_str}")
    return "\n".join(lines)


def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_favorite_item(event: Event) -> str:
    now = datetime.now(tz=UTC)
    badge = ""
    if getattr(event, "start_at_confirmed", True) and _coerce_utc(event.start_at) < now:
        badge = " · ⏹ завершилось"
    date_line = ""
    if getattr(event, "start_at_confirmed", True):
        start = _coerce_utc(event.start_at)
        date_line = f"\n📅 {start.strftime('%d.%m.%Y')}"
    return f"❤️ {_escape_html(strip_html(event.title))}{badge}{date_line}"
