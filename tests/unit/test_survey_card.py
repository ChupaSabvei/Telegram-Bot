from __future__ import annotations

from datetime import UTC, datetime, timedelta

from unittest.mock import MagicMock

import pytest

from src.bot.formatters.survey_card import _display_text, format_simple_card, format_survey_card, _summary_lines
from src.storage.repositories.events import EventRepository
from src.storage.schemas import EventDTO


@pytest.mark.asyncio
async def test_format_survey_card_contains_title_price_navigator(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://example.com/event/card",
            source_slug="kudago",
            title="Тестовая карточка",
            description="Краткое описание. Второе предложение.",
            category_slug="concerts",
            activity_slug="culture",
            city_slug="moscow",
            venue="Клуб",
            address="Москва, Тверская 1",
            start_at=datetime.now(tz=UTC) + timedelta(days=3),
            price_type="paid",
            price_text="от 900 ₽",
            price_amount_rub=900,
            venue_format="indoor",
        )
        event = await repo.upsert_event(dto)
        await session.commit()
        event = await repo.get_by_id(event.id)
        assert event is not None

    text = format_survey_card(event, audience="family", budget="3000")

    assert "Тестовая карточка" in text
    assert "900" in text
    assert "📅" in text
    assert "МСК" in text
    assert "Навигатор" in text
    assert "yandex.ru/maps" in text
    assert "Подробнее" in text


def test_format_favorite_item_handles_naive_datetime() -> None:
    from src.bot.formatters.survey_card import format_favorite_item

    event = MagicMock()
    event.title = "Прошедший концерт"
    event.start_at = datetime(2020, 1, 1)
    text = format_favorite_item(event)
    assert "завершилось" in text


def test_display_text_unescapes_html_entities() -> None:
    assert _display_text("Баян &amp; Аккордеон") == "Баян &amp; Аккордеон"
    assert "&amp;amp;" not in _display_text("Баян &amp; Аккордеон")


def test_summary_lines_strips_html() -> None:
    html = (
        '<p>Органист Даниэль Сальвадор представит <a class="external-link" '
        'href="https://example.com/program">авторскую программу</a> с контрастами.</p>'
    )
    lines = _summary_lines(html)
    assert lines
    assert "<" not in lines[0]
    assert "Органист Даниэль Сальвадор" in lines[0]
    assert "авторскую программу" in lines[0]


@pytest.mark.asyncio
async def test_format_survey_card_strips_html_description(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://example.com/event/html",
            source_slug="kudago",
            title="Концерт «Светотень»",
            description=(
                '<p>Органист представит <a href="https://example.com">программу</a> '
                "с контрастами света и тени.</p>"
            ),
            category_slug="concerts",
            activity_slug="culture",
            city_slug="moscow",
            venue="Собор",
            start_at=datetime.now(tz=UTC) + timedelta(days=3),
            price_type="paid",
            price_text="от 800 рублей",
            venue_format="indoor",
        )
        event = await repo.upsert_event(dto)
        await session.commit()
        event = await repo.get_by_id(event.id)
        assert event is not None

    text = format_survey_card(event, audience="solo", budget="unlimited")

    body, _links = text.split("🔗", maxsplit=1)
    assert "<p>" not in body
    assert "Органист представит программу" in body
    assert '<a href="https://example.com/event/html">Подробнее</a>' in text


@pytest.mark.asyncio
async def test_format_survey_card_adds_post_link_for_telegram_vk_source(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://t.me/TOT_STANDUP/1234",
            source_slug="telegram_channels",
            title="Пост из Telegram",
            description="Ссылка на пост должна быть отдельной строкой.",
            category_slug="other",
            activity_slug="culture",
            city_slug="moscow",
            venue="Telegram канал",
            start_at=datetime.now(tz=UTC) + timedelta(days=3),
            price_type="free",
            venue_format="indoor",
        )
        event = await repo.upsert_event(dto)
        await session.commit()
        event = await repo.get_by_id(event.id)
        assert event is not None

    text = format_survey_card(event, audience="solo", budget="free")
    assert "Пост в источнике" in text
    assert '<a href="https://t.me/TOT_STANDUP/1234">Пост в источнике</a>' in text


@pytest.mark.asyncio
async def test_format_simple_card_hides_survey_header(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://example.com/event/simple",
            source_slug="kudago",
            title="Простая карточка",
            description="Описание для карточки.",
            category_slug="other",
            activity_slug="culture",
            city_slug="moscow",
            venue="Зал",
            start_at=datetime.now(tz=UTC) + timedelta(days=2),
            price_type="free",
            venue_format="indoor",
        )
        event = await repo.upsert_event(dto)
        await session.commit()
        event = await repo.get_by_id(event.id)
        assert event is not None

    text = format_simple_card(event)
    assert not text.startswith("🤖 Для ")
    assert "🧩 Простая карточка" in text


@pytest.mark.asyncio
async def test_format_survey_card_hides_unconfirmed_date(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://t.me/kuda_v_moskva/4751",
            source_slug="telegram_channels",
            title="Лесная библиотека, парк 50-летия Октября",
            description="Лесная библиотека в парке.",
            category_slug="other",
            activity_slug="culture",
            city_slug="moscow",
            venue="Telegram: @kuda_v_moskva",
            start_at=datetime.now(tz=UTC) + timedelta(days=7),
            start_at_confirmed=False,
            price_type="unknown",
            venue_format="outdoor",
        )
        event = await repo.upsert_event(dto)
        await session.commit()
        event = await repo.get_by_id(event.id)
        assert event is not None

    text = format_survey_card(event, audience="couple", budget="1000")
    assert "📅" not in text
    assert "Лесная библиотека" in text


@pytest.mark.asyncio
async def test_format_survey_card_uses_date_from_social_post_text(db_runtime) -> None:
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        dto = EventDTO(
            source_url="https://t.me/mcktime/20239",
            source_slug="telegram_channels",
            title="Креативная тусовка",
            description="Когда: 18 июня 18:00 - 23:00. м. Тверская",
            category_slug="other",
            activity_slug="culture",
            city_slug="moscow",
            venue="Telegram: @mcktime",
            # Simulate stale publish timestamp saved in DB.
            start_at=datetime(2026, 6, 22, 0, 2, tzinfo=UTC),
            start_at_confirmed=True,
            price_type="free",
            venue_format="indoor",
        )
        event = await repo.upsert_event(dto)
        await session.commit()
        event = await repo.get_by_id(event.id)
        assert event is not None

    text = format_survey_card(event, audience="couple", budget="1000")
    assert "18.06." in text
    assert "22.06." not in text
