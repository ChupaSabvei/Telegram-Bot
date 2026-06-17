from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jsonschema import Draft7Validator

from src.storage.schemas import EventDTO


def test_event_dto_matches_v2_contract_schema() -> None:
    schema_path = Path("specs/002-multi-source-survey-flow/contracts/event-schema-v2.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)

    dto = EventDTO(
        source_url="https://example.com/event/1",
        source_slug="timepad",
        title="Джазовый концерт",
        description="Вечер живой музыки",
        category_slug="concerts",
        activity_slug="culture",
        city_slug="moscow",
        venue="Клуб",
        address="Москва, ул. Примерная, 1",
        start_at=datetime.now(tz=UTC) + timedelta(days=2),
        end_at=None,
        price_type="paid",
        price_text="от 1500 ₽",
        price_amount_rub=1500,
        venue_format="indoor",
        audience_tags=["couple"],
        is_online=False,
        popularity_score=42,
        image_url="https://example.com/image.jpg",
    )
    payload = dto.model_dump(mode="json")
    errors = list(validator.iter_errors(payload))
    assert errors == []
