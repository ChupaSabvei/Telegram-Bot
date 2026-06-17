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
}


def city_keyboard(*, include_back: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"city:{slug}")]
        for slug, label in CITY_LABELS.items()
    ]
    if include_back:
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def category_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=CATEGORY_LABELS[slug], callback_data=f"cat:{slug}")]
        for slug in CATEGORY_SLUGS
    ]
    rows.append([InlineKeyboardButton(text="⚙️ Настройки", callback_data="back:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def events_keyboard(event_ids: list[str], titles: list[str] | None = None) -> InlineKeyboardMarkup:
    rows = []
    for idx, event_id in enumerate(event_ids):
        label = f"▸ {idx + 1}"
        if titles and idx < len(titles):
            prefix = f"▸ {idx + 1}. "
            title = titles[idx]
            max_title_len = 64 - len(prefix)
            if len(title) > max_title_len:
                title = title[: max_title_len - 1] + "…"
            label = f"{prefix}{title}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"evt:{event_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_card_keyboard(source_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Открыть", url=source_url)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back:list")],
        ]
    )
