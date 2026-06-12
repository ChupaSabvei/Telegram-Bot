from src.ai.intent import detect_search_mode, extract_place_topic


def test_detect_places_mode_for_billiards() -> None:
    assert detect_search_mode("Куда можно сходить на бильярд?") == "places"


def test_detect_places_mode_for_bowling() -> None:
    assert detect_search_mode("боулинг в москве") == "places"


def test_detect_events_mode_for_concert() -> None:
    assert detect_search_mode("джазовый концерт в субботу") == "events"


def test_detect_events_mode_for_weekend_broad_query() -> None:
    assert detect_search_mode("чем заняться на выходных") == "events"


def test_extract_place_topic_from_billiard_query() -> None:
    topic = extract_place_topic("Куда можно сходить на бильярд?")
    assert "бильярд" in topic
