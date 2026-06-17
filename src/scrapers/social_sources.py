from __future__ import annotations

SOCIAL_SOURCE_SLUGS = frozenset({"telegram_channels"})


def should_use_social_sources(*, kudago_count: int, non_kudago_non_social_count: int) -> bool:
    return kudago_count > 0 and non_kudago_non_social_count == 0


def should_use_social_sources_from_saved(city_saved_by_source: dict[str, int]) -> bool:
    kudago_count = city_saved_by_source.get("kudago", 0)
    non_kudago_non_social_count = sum(
        saved
        for source_slug, saved in city_saved_by_source.items()
        if source_slug not in SOCIAL_SOURCE_SLUGS and source_slug != "kudago"
    )
    return should_use_social_sources(
        kudago_count=kudago_count,
        non_kudago_non_social_count=non_kudago_non_social_count,
    )
