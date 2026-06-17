from __future__ import annotations

import re

from src.storage.schemas import ActivitySlug, AudienceTag, EventDTO, VenueFormat

KIDS_PATTERN = re.compile(r"дет|kids|семейн|family|для детей", re.I)
GASTRO_PATTERN = re.compile(r"food|ресторан|гастро|дегуст|кухн|ужин", re.I)
RELAX_PATTERN = re.compile(r"spa|йога|wellness|релакс|медитац", re.I)
SPORT_PATTERN = re.compile(r"спорт|sport|футбол|бег|трениров|матч|turnir|турнир", re.I)
NON_SPORT_PATTERN = re.compile(r"стендап|standup|stand-up|комик|джаз|оперет|спектакл|концерт|театр", re.I)
CULTURE_PATTERN = re.compile(r"концерт|театр|выстав|форум|лекци|культур", re.I)

SOURCE_ACTIVITY: dict[str, ActivitySlug] = {
    "mos_sport_rayon": "sport",
    "mtpp": "culture",
}

CATEGORY_ACTIVITY: dict[str, ActivitySlug] = {
    "sport": "sport",
    "concerts": "culture",
    "theater": "culture",
    "exhibitions": "culture",
    "education": "kids",
}


def classify_activity_rule(dto: EventDTO) -> ActivitySlug | None:
    if dto.activity_slug:
        return dto.activity_slug

    if dto.source_slug in SOURCE_ACTIVITY:
        return SOURCE_ACTIVITY[dto.source_slug]

    mapped = CATEGORY_ACTIVITY.get(dto.category_slug)
    if mapped:
        return mapped

    text = f"{dto.title} {dto.description or ''}"
    if NON_SPORT_PATTERN.search(text) and dto.category_slug in {"concerts", "theater", "exhibitions"}:
        return "culture"
    if KIDS_PATTERN.search(text):
        return "kids"
    if GASTRO_PATTERN.search(text):
        return "gastro"
    if RELAX_PATTERN.search(text):
        return "relax"
    if SPORT_PATTERN.search(text):
        return "sport"
    if CULTURE_PATTERN.search(text):
        return "culture"
    if "семей" in text.lower():
        return "family"
    return None


def infer_venue_format(dto: EventDTO) -> VenueFormat:
    if dto.venue_format != "unknown":
        return dto.venue_format
    if dto.is_online:
        return "online"
    if dto.source_slug == "mos_sport_rayon":
        return "outdoor"
    text = f"{dto.title} {dto.description or ''} {dto.venue or ''}".lower()
    if any(word in text for word in ("онлайн", "online", "трансляц")):
        return "online"
    if any(word in text for word in ("парк", "улиц", "open air", "на улице")):
        return "outdoor"
    if any(word in text for word in ("музей", "театр", "клуб", "зал", "центр")):
        return "indoor"
    return "unknown"


def infer_audience_tags(dto: EventDTO) -> list[AudienceTag]:
    if dto.audience_tags:
        return list(dto.audience_tags)
    tags: list[AudienceTag] = []
    text = f"{dto.title} {dto.description or ''}".lower()
    if "дет" in text:
        tags.append("kids")
    if "семей" in text or dto.activity_slug == "family":
        tags.append("family")
    return tags


def parse_price_amount_rub(dto: EventDTO) -> int | None:
    if dto.price_amount_rub is not None:
        return dto.price_amount_rub
    if dto.price_type == "free":
        return 0
    if not dto.price_text:
        return None
    match = re.search(r"(\d[\d\s]*)", dto.price_text.replace("\u00a0", " "))
    if match:
        try:
            return int(match.group(1).replace(" ", ""))
        except ValueError:
            return None
    return None
