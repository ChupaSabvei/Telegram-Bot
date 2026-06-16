from __future__ import annotations

from typing import Literal

SearchMode = Literal["events", "places"]

PLACE_KEYWORDS = (
    "бильярд",
    "боулинг",
    "bowling",
    "пляж",
    "загора",
    "загор",
    "купан",
    "купа",
    "баня",
    "сауна",
    "караоке",
    "аквапарк",
    "океанариум",
    "зоопарк",
    "картинг",
    "лазертаг",
    "скалодром",
    "батут",
    "антикаф",
    "anticafe",
    "настольн",
    "переговорн",
    "ресторан",
    "кафе",
    "кофейн",
    "гастропаб",
    "паб ",
    " ночной клуб",
    "клуб ",
    "боулинг",
    "стрелков",
    "тир ",
    "каток",
    "vr-",
    " vr ",
)

PLACE_PATTERNS = (
    "сходить на",
    "сходить в",
    "поиграть в",
    "поиграть на",
    "где позагора",
    "где покупать",
    "где покататься",
    "где поесть",
    "куда сходить на",
    "куда сходить в",
    "где найти",
)

EVENT_KEYWORDS = (
    "концерт",
    "спектакл",
    "выставк",
    "театр",
    "джazz",
    "джаз",
    "фестиваль",
    "стендап",
    "stand-up",
    "standup",
    "лекци",
    "семинар",
    "мюзикл",
    "опера",
    "балет",
    "филармон",
    "оркестр",
    "цирк",
    "шоу ",
    "мероприят",
    "афиш",
)


def detect_search_mode(query: str) -> SearchMode:
    lowered = query.lower().strip()
    has_place = any(keyword in lowered for keyword in PLACE_KEYWORDS)
    has_event = any(keyword in lowered for keyword in EVENT_KEYWORDS)
    has_place_pattern = any(pattern in lowered for pattern in PLACE_PATTERNS)

    if has_place and not has_event:
        return "places"
    if has_place_pattern and not has_event:
        return "places"
    return "events"


def extract_place_topic(query: str) -> str:
    lowered = query.lower()
    for keyword in PLACE_KEYWORDS:
        if keyword in lowered:
            return keyword.strip()
    if "сходить на" in lowered:
        return lowered.split("сходить на", maxsplit=1)[1].strip(" ?.")[:40]
    if "сходить в" in lowered:
        return lowered.split("сходить в", maxsplit=1)[1].strip(" ?.")[:40]
    return query.strip()[:60]
