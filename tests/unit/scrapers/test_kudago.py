from __future__ import annotations

from datetime import UTC, datetime

from src.scrapers.event_dates import MSK
from src.scrapers.kudago import _pick_start_at


def test_kudago_pick_start_at_keeps_unix_timestamp_in_utc() -> None:
    start_ts = int(datetime(2026, 6, 20, 16, 0, tzinfo=UTC).timestamp())

    picked = _pick_start_at(
        [{"start": start_ts}],
        now=datetime(2026, 6, 15, tzinfo=UTC),
        horizon=datetime(2026, 7, 15, tzinfo=UTC),
    )

    assert picked is not None
    assert picked == datetime(2026, 6, 20, 16, 0, tzinfo=UTC)
    assert picked.astimezone(MSK) == datetime(2026, 6, 20, 19, 0, tzinfo=MSK)
