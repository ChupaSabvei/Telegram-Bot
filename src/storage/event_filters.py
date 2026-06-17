from __future__ import annotations

from datetime import datetime

BLOCKED_URL_PARTS = (
    "/places/",
    "/collections/",
    "/venues/",
)


def is_publishable_event_url(source_url: str) -> bool:
    lowered = str(source_url).lower()
    return not any(part in lowered for part in BLOCKED_URL_PARTS)


def is_plausible_event_timestamp(start_at: datetime, *, synced_at: datetime | None = None) -> bool:
    if start_at.tzinfo is None:
        return False
    if synced_at is None:
        return True
    if start_at.microsecond == 0:
        return True
    return abs((start_at - synced_at).total_seconds()) >= 120
