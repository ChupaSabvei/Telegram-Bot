from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.ai.activity_classifier import ActivityClassifier
from src.scrapers.classifiers.activity import classify_activity_rule
from src.scrapers.runner import enrich_event_dto
from src.storage.schemas import EventDTO


def _dto(**overrides) -> EventDTO:
    base = dict(
        source_url="https://example.com/event/1",
        source_slug="kudago",
        title="Событие",
        description=None,
        category_slug="other",
        city_slug="moscow",
        start_at=datetime.now(tz=UTC) + timedelta(days=5),
    )
    base.update(overrides)
    return EventDTO(**base)


def test_classify_activity_rule_by_sport_keyword() -> None:
    dto = _dto(title="Футбольный турнир", description="Спортивное мероприятие")
    assert classify_activity_rule(dto) == "sport"


def test_classify_activity_rule_by_source_slug() -> None:
    dto = _dto(source_slug="mos_sport_rayon", title="Занятие")
    assert classify_activity_rule(dto) == "sport"


def test_classify_activity_rule_by_category() -> None:
    dto = _dto(category_slug="concerts", title="Вечер")
    assert classify_activity_rule(dto) == "culture"


@pytest.mark.asyncio
async def test_ai_classifier_unavailable_returns_none() -> None:
    classifier = ActivityClassifier(client=None)
    dto = _dto(title="Неочевидное событие", description="без ключевых слов")
    assert await classifier.classify(dto) is None


@pytest.mark.asyncio
async def test_enrich_event_dto_without_ai_keeps_rule_based_slug() -> None:
    classifier = ActivityClassifier(client=None)
    dto = _dto(title="Йога на крыше", description="релакс программа")
    enriched = await enrich_event_dto(dto, classifier)
    assert enriched.activity_slug == "relax"
