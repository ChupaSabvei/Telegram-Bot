from __future__ import annotations

import pytest

from src.scrapers.social_sources import should_use_social_sources, should_use_social_sources_from_saved


def test_should_use_social_sources_when_only_kudago_has_data() -> None:
    assert should_use_social_sources(kudago_count=5, non_kudago_non_social_count=0) is True


def test_should_not_use_social_sources_when_other_sites_have_data() -> None:
    assert should_use_social_sources(kudago_count=5, non_kudago_non_social_count=1) is False


def test_should_not_use_social_sources_without_kudago() -> None:
    assert should_use_social_sources(kudago_count=0, non_kudago_non_social_count=0) is False


def test_should_use_social_sources_from_saved_counts() -> None:
    saved = {"kudago": 10, "timepad": 0, "telegram_channels": 3}
    assert should_use_social_sources_from_saved(saved) is True

    saved_with_other = {"kudago": 10, "timepad": 2, "telegram_channels": 3}
    assert should_use_social_sources_from_saved(saved_with_other) is False
