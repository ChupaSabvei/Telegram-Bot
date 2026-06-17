from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from src.bot.formatters.events import _escape_html, strip_html
from src.storage.event_times import display_time_confirmed, resolve_display_start
from src.storage.models import Event, EventCollection

MSK = timezone(timedelta(hours=3))

COLLECTION_VIEW_INSTRUCTION = (
    "Чтобы увидеть подборку, необходимо нажать /start и выбрать нужный город."
)


def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _event_date_line(event: Event) -> str:
    display_start = resolve_display_start(event)
    if display_start is None or not display_time_confirmed(event, display_start):
        return ""
    local = _coerce_utc(display_start).astimezone(MSK)
    return local.strftime("%d.%m · %H:%M")


def format_collection_summary(collection: EventCollection, *, events_count: int) -> str:
    return f"📋 {_escape_html(collection.title)} — {events_count} событ."


def format_collections_index(collections: list[EventCollection]) -> str:
    if not collections:
        return (
            "📋 У вас пока нет подборок.\n\n"
            "Создайте подборку из избранного и отправьте ссылку друзьям.\n\n"
            f"{COLLECTION_VIEW_INSTRUCTION}"
        )
    lines = ["📋 Ваши подборки:\n"]
    for idx, item in enumerate(collections, start=1):
        count = len(item.items)
        lines.append(f"{idx}. {_escape_html(item.title)} — {count} событ.")
    return "\n".join(lines)


def format_shared_collection_header(collection: EventCollection, *, events: list[Event]) -> str:
    lines = [
        f"📋 <b>{_escape_html(collection.title)}</b>",
        f"<i>{len(events)} мероприятий — можно сохранить себе или открыть по одному</i>",
        "",
    ]
    for idx, event in enumerate(events, start=1):
        title = _escape_html(strip_html(event.title))
        date_line = _event_date_line(event) or "дата уточняется"
        venue = _escape_html(strip_html(event.venue or event.address or "место уточняется"))
        lines.append(f"<b>{idx}.</b> {title}")
        lines.append(f"   📅 {_escape_html(date_line)}")
        lines.append(f"   📍 {venue}")
    return "\n".join(lines)
