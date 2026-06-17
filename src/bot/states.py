from aiogram.fsm.state import State, StatesGroup


class BotStates(StatesGroup):
    ONBOARDING_CITY = State()
    MAIN_MENU = State()
    BROWSING_CATEGORY = State()
    VIEWING_EVENT = State()
    SETTINGS_CITY = State()
    AI_SEARCH = State()
    SURVEY_AUDIENCE = State()
    SURVEY_ACTIVITY = State()
    SURVEY_BUDGET = State()
    SURVEY_RESULT = State()
    POPULAR_LIST = State()
    FAVORITES_LIST = State()
    COLLECTIONS_LIST = State()
    COLLECTION_VIEW = State()
    COLLECTION_RENAME = State()
    COLLECTION_EDIT = State()
    SHARED_COLLECTION = State()
