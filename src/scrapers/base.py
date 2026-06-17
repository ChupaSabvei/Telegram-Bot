from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.storage.schemas import EventDTO


class ScraperProtocol(Protocol):
    slug: str
    name: str
    supported_cities: tuple[str, ...]

    async def fetch_events(self, city_slug: str) -> list[EventDTO]:
        """Fetch normalized events for one city and never raise."""


@dataclass(slots=True)
class ScraperRegistry:
    scrapers: list[ScraperProtocol]

    def list_active(self) -> list[ScraperProtocol]:
        return list(self.scrapers)
