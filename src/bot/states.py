from aiogram.fsm.state import State, StatesGroup


class BotStates(StatesGroup):
    ONBOARDING_CITY = State()
    MAIN_MENU = State()
    BROWSING_CATEGORY = State()
    VIEWING_EVENT = State()
    SETTINGS_CITY = State()
    AI_SEARCH = State()
