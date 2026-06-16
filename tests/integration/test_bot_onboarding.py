from __future__ import annotations

import pytest

from src.bot.states import BotStates


@pytest.mark.asyncio
async def test_onboarding_state_name() -> None:
    assert BotStates.ONBOARDING_CITY.state.endswith("ONBOARDING_CITY")
