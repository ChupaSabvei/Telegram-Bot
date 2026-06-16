from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from src.scrapers.kudago import KudaGoScraper
from src.scrapers.yandex_afisha import YandexAfishaScraper


@pytest.fixture()
def event_validator() -> Draft7Validator:
    schema_path = Path("specs/001-ai-event-discovery/contracts/event-schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft7Validator(schema)


@pytest.mark.asyncio
async def test_kudago_scraper_output_contract(event_validator: Draft7Validator, monkeypatch) -> None:
    now = datetime.now(tz=UTC)
    payload = {
        "results": [
            {
                "id": 1,
                "title": "Выставка",
                "description": "Описание",
                "dates": [{"start": int((now + timedelta(days=1)).timestamp())}],
                "place": {"title": "Галерея"},
                "price": "Бесплатно",
                "is_free": True,
                "site_url": "https://example.com/kudago/event-1",
                "categories": ["exhibition"],
                "images": [{"image": "https://example.com/img.jpg"}],
            }
        ]
    }

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            return DummyResponse()

    monkeypatch.setattr("src.scrapers.kudago.httpx.AsyncClient", lambda *a, **k: DummyClient())

    scraper = KudaGoScraper()
    items = await scraper.fetch_events("moscow")
    assert items
    for item in items:
        errors = list(event_validator.iter_errors(item.model_dump(mode="json")))
        assert errors == []


@pytest.mark.asyncio
async def test_yandex_scraper_output_contract(event_validator: Draft7Validator, monkeypatch) -> None:
    start = (datetime.now(tz=UTC) + timedelta(days=2)).isoformat()
    html = f"""
    <div data-event-card="1"
         data-title="Театральная постановка"
         data-url="https://example.com/yandex/event-1"
         data-start-at="{start}"
         data-venue="Театр"
         data-category="theater"
         data-price="от 1000 ₽"
         data-image-url="https://example.com/i.png"
         data-description="Описание спектакля"></div>
    """

    class DummyResponse:
        text = html
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            return DummyResponse()

    async def no_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("src.scrapers.yandex_afisha.httpx.AsyncClient", lambda *a, **k: DummyClient())
    monkeypatch.setattr("src.scrapers.yandex_afisha.asyncio.sleep", no_sleep)

    scraper = YandexAfishaScraper()
    items = await scraper.fetch_events("moscow")
    assert items
    for item in items:
        errors = list(event_validator.iter_errors(item.model_dump(mode="json")))
        assert errors == []
