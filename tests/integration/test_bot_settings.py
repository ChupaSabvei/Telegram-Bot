from __future__ import annotations

import pytest

from src.bot.states import BotStates


@pytest.mark.asyncio
async def test_settings_state_name() -> None:
    assert BotStates.SETTINGS_CITY.state.endswith("SETTINGS_CITY")
