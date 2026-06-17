from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class CitySlug(StrEnum):
    MOSCOW = "moscow"
    SPB = "spb"


CATEGORY_SLUGS = (
    "concerts",
    "exhibitions",
    "theater",
    "sport",
    "education",
    "other",
)

ACTIVITY_SLUGS = ("sport", "kids", "family", "culture", "gastro", "relax")
VENUE_FORMATS = ("indoor", "outdoor", "mixed", "online", "unknown")
AUDIENCE_TAGS = ("solo", "couple", "family", "friends", "kids")

SOURCE_SLUGS = (
    "yandex_afisha",
    "kudago",
    "timepad",
    "mts_live",
    "tbank_gorod",
    "mos_kultura",
    "timeout_msk",
    "mos_sport_rayon",
    "mtpp",
    "telegram_channels",
)

PriceType = Literal["free", "paid", "unknown"]
CategorySlug = Literal["concerts", "exhibitions", "theater", "sport", "education", "other"]
ActivitySlug = Literal["sport", "kids", "family", "culture", "gastro", "relax"]
VenueFormat = Literal["indoor", "outdoor", "mixed", "online", "unknown"]
AudienceTag = Literal["solo", "couple", "family", "friends", "kids"]
SourceSlug = Literal[
    "yandex_afisha",
    "kudago",
    "timepad",
    "mts_live",
    "tbank_gorod",
    "mos_kultura",
    "timeout_msk",
    "mos_sport_rayon",
    "mtpp",
    "telegram_channels",
]


class EventDTO(BaseModel):
    external_id: str | None = None
    source_url: HttpUrl
    source_slug: SourceSlug
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    category_slug: CategorySlug
    activity_slug: ActivitySlug | None = None
    city_slug: str
    venue: str | None = None
    address: str | None = None
    start_at: datetime
    start_at_confirmed: bool = True
    session_starts_at: list[datetime] = Field(default_factory=list)
    end_at: datetime | None = None
    price_type: PriceType = "unknown"
    price_text: str | None = None
    price_amount_rub: int | None = Field(default=None, ge=0)
    venue_format: VenueFormat = "unknown"
    audience_tags: list[AudienceTag] = Field(default_factory=list)
    is_online: bool = False
    popularity_score: int = Field(default=0, ge=0)
    image_url: HttpUrl | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def normalize_dt(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_validator("session_starts_at", mode="before")
    @classmethod
    def normalize_sessions(cls, value: list | None) -> list[datetime]:
        if not value:
            return []
        normalized: list[datetime] = []
        for item in value:
            parsed = cls.normalize_dt(item)
            if parsed is not None:
                normalized.append(parsed)
        return normalized

    @field_validator("city_slug")
    @classmethod
    def validate_city_slug(cls, value: str) -> str:
        known = {item.value for item in CitySlug}
        if value not in known:
            raise ValueError(f"Unsupported city_slug: {value}")
        return value

    @field_validator("venue", "address")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None
