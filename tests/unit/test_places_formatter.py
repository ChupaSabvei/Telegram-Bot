from src.ai.places import PlaceItem, PlacesResponse
from src.bot.formatters.places import format_places_response


def test_format_places_response_contains_maps_link() -> None:
    response = PlacesResponse(
        topic="бильярд",
        city_slug="moscow",
        places=[
            PlaceItem(
                name="Cue Club",
                district="Центр",
                note="Несколько столов и бар",
                price_hint="от 600 ₽/час",
                maps_url="https://yandex.ru/maps/?text=Cue+Club+Moscow",
            )
        ],
        tip="Лучше бронировать вечером заранее",
    )
    text = format_places_response(response)
    assert "Cue Club" in text
    assert "Яндекс.Картах" in text
    assert "🎱" in text
