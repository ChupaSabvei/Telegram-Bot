from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.storage.schemas import CATEGORY_SLUGS, CitySlug

CATEGORY_LABELS = {
    "concerts": "Концерты",
    "exhibitions": "Выставки",
    "theater": "Театр",
    "sport": "Спорт",
    "education": "Образование",
    "other": "Другое",
}

CITY_LABELS = {
    CitySlug.MOSCOW.value: "Москва",
    CitySlug.SPB.value: "Санкт-Петербург",
    CitySlug.NOVOSIBIRSK.value: "Новосибирск",
    CitySlug.YEKATERINBURG.value: "Екатеринбург",
    CitySlug.KAZAN.value: "Казань",
    CitySlug.NIZHNY_NOVGOROD.value: "Нижний Новгород",
    CitySlug.CHELYABINSK.value: "Челябинск",
    CitySlug.SAMARA.value: "Самара",
    CitySlug.OMSK.value: "Омск",
    CitySlug.ROSTOV_ON_DON.value: "Ростов-на-Дону",
    CitySlug.UFA.value: "Уфа",
    CitySlug.KRASNOYARSK.value: "Красноярск",
    CitySlug.VORONEZH.value: "Воронеж",
    CitySlug.PERM.value: "Пермь",
    CitySlug.VOLGOGRAD.value: "Волгоград",
}


def city_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"city:{slug}")]
        for slug, label in CITY_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def category_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=CATEGORY_LABELS[slug], callback_data=f"cat:{slug}")]
        for slug in CATEGORY_SLUGS
    ]
    rows.append([InlineKeyboardButton(text="⚙️ Настройки", callback_data="back:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def events_keyboard(event_ids: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"Открыть #{idx + 1}", callback_data=f"evt:{event_id}")]
            for idx, event_id in enumerate(event_ids)]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_card_keyboard(source_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Открыть", url=source_url)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back:list")],
        ]
    )
