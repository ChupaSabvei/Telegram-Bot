from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from src.ai.client import OpenAIClient
from src.bot.keyboards.menus import CITY_LABELS


@dataclass(slots=True)
class PlaceItem:
    name: str
    district: str | None
    note: str | None
    price_hint: str | None
    maps_url: str


@dataclass(slots=True)
class PlacesResponse:
    topic: str
    city_slug: str
    places: list[PlaceItem]
    tip: str | None
    fallback_used: bool = False


class PlaceAdvisor:
    def __init__(self, llm_client: OpenAIClient) -> None:
        self.llm_client = llm_client

    async def recommend(self, query: str, city_slug: str, topic: str) -> PlacesResponse:
        city_name = CITY_LABELS.get(city_slug, city_slug)
        try:
            raw = await self.llm_client.recommend_places(
                query=query,
                city_name=city_name,
                topic=topic,
            )
            places = [
                PlaceItem(
                    name=item["name"],
                    district=item.get("district"),
                    note=item.get("note"),
                    price_hint=item.get("price_hint"),
                    maps_url=_maps_url(item["name"], city_name),
                )
                for item in raw.get("places", [])[:8]
                if item.get("name")
            ]
            if places:
                return PlacesResponse(
                    topic=topic,
                    city_slug=city_slug,
                    places=places,
                    tip=raw.get("tip"),
                )
        except Exception:
            pass

        return PlacesResponse(
            topic=topic,
            city_slug=city_slug,
            places=[],
            tip=(
                f"Не удалось собрать подборку мест. "
                f"Попробуйте поиск в Яндекс.Картах: «{topic} {city_name}»."
            ),
            fallback_used=True,
        )


def _maps_url(name: str, city_name: str) -> str:
    return f"https://yandex.ru/maps/?text={quote(f'{name} {city_name}')}"
