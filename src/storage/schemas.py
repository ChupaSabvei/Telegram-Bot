from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class CitySlug(StrEnum):
    MOSCOW = "moscow"
    SPB = "spb"
    NOVOSIBIRSK = "novosibirsk"
    YEKATERINBURG = "yekaterinburg"
    KAZAN = "kazan"
    NIZHNY_NOVGOROD = "nizhny_novgorod"
    CHELYABINSK = "chelyabinsk"
    SAMARA = "samara"
    OMSK = "omsk"
    ROSTOV_ON_DON = "rostov_on_don"
    UFA = "ufa"
    KRASNOYARSK = "krasnoyarsk"
    VORONEZH = "voronezh"
    PERM = "perm"
    VOLGOGRAD = "volgograd"


CATEGORY_SLUGS = (
    "concerts",
    "exhibitions",
    "theater",
    "sport",
    "education",
    "other",
)

SOURCE_SLUGS = ("yandex_afisha", "kudago")

PriceType = Literal["free", "paid", "unknown"]
CategorySlug = Literal["concerts", "exhibitions", "theater", "sport", "education", "other"]
SourceSlug = Literal["yandex_afisha", "kudago"]


class EventDTO(BaseModel):
    external_id: str | None = None
    source_url: HttpUrl
    source_slug: SourceSlug
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    category_slug: CategorySlug
    city_slug: str
    venue: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    price_type: PriceType = "unknown"
    price_text: str | None = None
    is_online: Literal[False] = False
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

    @field_validator("city_slug")
    @classmethod
    def validate_city_slug(cls, value: str) -> str:
        known = {item.value for item in CitySlug}
        if value not in known:
            raise ValueError(f"Unsupported city_slug: {value}")
        return value

    @field_validator("venue")
    @classmethod
    def strip_venue(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None
