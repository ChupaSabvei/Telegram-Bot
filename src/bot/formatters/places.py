from __future__ import annotations

from src.ai.places import PlaceItem, PlacesResponse
from src.bot.formatters.events import _escape_html
from src.bot.keyboards.menus import CITY_LABELS

TOPIC_EMOJI = {
    "бильярд": "🎱",
    "боулинг": "🎳",
    "пляж": "🏖",
    "загора": "🏖",
    "купан": "🏊",
    "баня": "🧖",
    "сауна": "🧖",
    "караоке": "🎤",
    "аквапарк": "💦",
    "океанариум": "🐠",
    "зоопарк": "🦁",
    "картинг": "🏎",
    "лазертаг": "🔫",
    "скалодром": "🧗",
    "батут": "🤸",
    "ресторан": "🍽",
    "кафе": "☕",
}


def format_places_response(response: PlacesResponse) -> str:
    city_name = CITY_LABELS.get(response.city_slug, response.city_slug)
    emoji = _topic_emoji(response.topic)
    topic_label = _escape_html(response.topic.capitalize())

    if not response.places:
        tip = response.tip or "Попробуйте уточнить запрос или выберите категорию в меню."
        return (
            f"{emoji} <b>{topic_label}</b> · {_escape_html(city_name)}\n\n"
            f"{_escape_html(tip)}"
        )

    lines = [
        f"{emoji} <b>{topic_label}</b> · {_escape_html(city_name)}",
        f"<i>{len(response.places)} мест — проверьте часы работы перед визитом</i>",
        "",
    ]
    for idx, place in enumerate(response.places, start=1):
        if idx > 1:
            lines.append("───────────────")
        lines.extend(_format_place(idx, place))

    lines.extend(
        [
            "",
            "<i>ℹ️ Подборка от ИИ — уточняйте адрес, цены и бронь на месте.</i>",
        ]
    )
    if response.tip:
        lines.extend(["", f"<i>{_escape_html(response.tip)}</i>"])
    return "\n".join(lines)


def _format_place(idx: int, place: PlaceItem) -> list[str]:
    rows = [f"<b>{idx}.</b> {_escape_html(place.name)}"]
    details: list[str] = []
    if place.district:
        details.append(f"📍 {_escape_html(place.district)}")
    if place.price_hint:
        details.append(f"💰 {_escape_html(place.price_hint)}")
    if details:
        rows.append("   " + " · ".join(details))
    if place.note:
        rows.append(f"   {_escape_html(place.note)}")
    rows.append(f'   <a href="{place.maps_url}">Открыть в Яндекс.Картах</a>')
    return rows


def _topic_emoji(topic: str) -> str:
    lowered = topic.lower()
    for key, emoji in TOPIC_EMOJI.items():
        if key in lowered:
            return emoji
    return "📍"
