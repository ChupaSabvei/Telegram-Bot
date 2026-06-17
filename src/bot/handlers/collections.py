from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.formatters.collections import (
    COLLECTION_VIEW_INSTRUCTION,
    format_collections_index,
    format_shared_collection_header,
)
from src.bot.formatters.events import EVENT_MESSAGE_PARSE_MODE, _escape_html
from src.bot.handlers.event_cards import show_viewing_event
from src.bot.keyboards.lists import (
    add_button_row,
    clean_button_label,
    collection_index_button_label,
    list_with_back_keyboard,
)
from src.bot.keyboards.main_menu import main_menu_keyboard
from src.bot.services.collection_share import build_collection_share_link, default_collection_title
from src.bot.states import BotStates
from src.storage.database import build_runtime
from src.storage.models import Event, EventCollection
from src.storage.repositories.collections import (
    MAX_ITEMS_PER_COLLECTION,
    CollectionRepository,
)
from src.storage.repositories.events import EventRepository
from src.storage.repositories.favorites import FavoritesRepository
from src.storage.repositories.users import UserSettingsRepository

router = Router()

MAX_TITLE_LEN = 120


def _collection_view_keyboard(collection_id: str, events: list[Event]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for idx, event in enumerate(events):
        add_button_row(
            builder,
            clean_button_label(event.title),
            f"col:ev:{collection_id}:{idx}",
        )
    add_button_row(builder, "✏️ Переименовать", f"col:rename:{collection_id}")
    add_button_row(builder, "✂️ Убрать события", f"col:edit:{collection_id}")
    add_button_row(builder, "📤 Поделиться", f"col:share:{collection_id}")
    add_button_row(builder, "🗑 Удалить подборку", f"col:del:{collection_id}")
    add_button_row(builder, "⬅️ К подборкам", "menu:collections")
    add_button_row(builder, "🏠 Меню", "nav:main")
    return builder


def _collection_edit_keyboard(collection_id: str, events: list[Event]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for idx, event in enumerate(events):
        add_button_row(
            builder,
            clean_button_label(event.title, prefix="❌ "),
            f"col:rm:{collection_id}:{idx}",
        )
    add_button_row(builder, "⬅️ Готово", f"col:view:{collection_id}")
    return builder


def _rename_cancel_keyboard(collection_id: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    add_button_row(builder, "⬅️ Отмена", f"col:view:{collection_id}")
    return builder


async def _load_owned_collection(
    collection_id: str,
    telegram_id: int,
) -> tuple[EventCollection, list[Event]] | None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        col_repo = CollectionRepository(session)
        collection = await col_repo.get_owned(collection_id, telegram_id)
        if collection is None:
            return None
        events = await col_repo.list_events(collection_id)
    return collection, events


def _event_at_index(events: list[Event], index: int) -> Event | None:
    if index < 0 or index >= len(events):
        return None
    return events[index]


async def _edit_collection_message(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    collection: EventCollection,
    events: list[Event],
    keyboard: InlineKeyboardBuilder,
    bot_state: BotStates,
    answer_text: str | None = None,
) -> None:
    text = format_shared_collection_header(collection, events=events)
    await state.set_state(bot_state)
    await state.update_data(current_collection_id=collection.id)
    try:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard.as_markup(),
            parse_mode=EVENT_MESSAGE_PARSE_MODE,
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            reply_markup=keyboard.as_markup(),
            parse_mode=EVENT_MESSAGE_PARSE_MODE,
        )
    if answer_text:
        await callback.answer(answer_text)
    else:
        await callback.answer()


async def render_collections_index(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        collections = await CollectionRepository(session).list_for_owner(callback.from_user.id)

    buttons = [
        (collection_index_button_label(item.title, events_count=len(item.items)), f"col:view:{item.id}")
        for item in collections
    ]
    extra = [("➕ Создать из избранного", "col:create")]
    kb = list_with_back_keyboard(buttons, extra_rows=extra)
    text = format_collections_index(collections)
    await state.set_state(BotStates.COLLECTIONS_LIST)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


async def show_shared_collection(
    target: Message | CallbackQuery,
    state: FSMContext,
    share_token: str,
) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        collection = await CollectionRepository(session).get_by_share_token(share_token)
        if collection is None:
            text = "Подборка не найдена или была удалена."
            if isinstance(target, CallbackQuery):
                await target.answer(text, show_alert=True)
            else:
                await target.answer(text, reply_markup=main_menu_keyboard())
            return
        events = await CollectionRepository(session).list_events(collection.id)

    if not events:
        text = "В этой подборке пока нет мероприятий."
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=main_menu_keyboard())
            await target.answer()
        else:
            await target.answer(text, reply_markup=main_menu_keyboard())
        return

    text = format_shared_collection_header(collection, events=events)
    kb = _shared_collection_keyboard(share_token, events).as_markup()
    await state.set_state(BotStates.SHARED_COLLECTION)
    await state.update_data(shared_token=share_token)

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
        except TelegramBadRequest:
            await target.message.answer(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)


def _shared_collection_keyboard(share_token: str, events: list) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for idx, event in enumerate(events):
        add_button_row(
            builder,
            clean_button_label(event.title),
            f"sh:ev:{share_token}:{idx}",
        )
    add_button_row(builder, "💾 Сохранить всё в избранное", f"sh:save:{share_token}")
    add_button_row(builder, "🏠 Меню", "nav:main")
    return builder


@router.callback_query(F.data == "menu:collections")
async def collections_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await render_collections_index(callback, state)


@router.callback_query(F.data == "col:create")
async def collection_create(callback: CallbackQuery, state: FSMContext) -> None:
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        fav_repo = FavoritesRepository(session)
        col_repo = CollectionRepository(session)
        favorites = await fav_repo.list_for_user(callback.from_user.id)
        if not favorites:
            await callback.answer("Сначала добавьте события в избранное ❤️", show_alert=True)
            return
        try:
            collection = await col_repo.create(
                callback.from_user.id,
                default_collection_title(),
            )
        except ValueError:
            await callback.answer("Достигнут лимит подборок — удалите старую", show_alert=True)
            return
        event_ids = [event.id for event in favorites[:MAX_ITEMS_PER_COLLECTION]]
        await col_repo.add_events(collection.id, event_ids)
        await session.commit()
        events = await col_repo.list_events(collection.id)

    await _edit_collection_message(
        callback,
        state,
        collection=collection,
        events=events,
        keyboard=_collection_view_keyboard(collection.id, events),
        bot_state=BotStates.COLLECTION_VIEW,
        answer_text="Подборка создана",
    )


@router.callback_query(F.data.startswith("col:view:"))
async def collection_view(callback: CallbackQuery, state: FSMContext) -> None:
    collection_id = callback.data.split(":")[-1]
    loaded = await _load_owned_collection(collection_id, callback.from_user.id)
    if loaded is None:
        await callback.answer("Подборка не найдена", show_alert=True)
        return
    collection, events = loaded
    await _edit_collection_message(
        callback,
        state,
        collection=collection,
        events=events,
        keyboard=_collection_view_keyboard(collection_id, events),
        bot_state=BotStates.COLLECTION_VIEW,
    )


@router.callback_query(F.data.startswith("col:edit:"))
async def collection_edit(callback: CallbackQuery, state: FSMContext) -> None:
    collection_id = callback.data.split(":")[-1]
    loaded = await _load_owned_collection(collection_id, callback.from_user.id)
    if loaded is None:
        await callback.answer("Подборка не найдена", show_alert=True)
        return
    collection, events = loaded
    if not events:
        await callback.answer("В подборке нет событий для удаления", show_alert=True)
        return

    text = (
        f"✂️ <b>{_escape_html(collection.title)}</b>\n\n"
        "Нажмите на событие, чтобы убрать его из подборки:"
    )
    kb = _collection_edit_keyboard(collection_id, events).as_markup()
    await state.set_state(BotStates.COLLECTION_EDIT)
    await state.update_data(current_collection_id=collection_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
    await callback.answer()


@router.callback_query(F.data.startswith("col:rename:"))
async def collection_rename_start(callback: CallbackQuery, state: FSMContext) -> None:
    collection_id = callback.data.split(":")[-1]
    loaded = await _load_owned_collection(collection_id, callback.from_user.id)
    if loaded is None:
        await callback.answer("Подборка не найдена", show_alert=True)
        return
    collection, _events = loaded

    text = (
        f"✏️ Текущее название: <b>{_escape_html(collection.title)}</b>\n\n"
        f"Отправьте новое название (до {MAX_TITLE_LEN} символов)."
    )
    kb = _rename_cancel_keyboard(collection_id).as_markup()
    await state.set_state(BotStates.COLLECTION_RENAME)
    await state.update_data(current_collection_id=collection_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
    await callback.answer()


@router.message(BotStates.COLLECTION_RENAME, F.text & ~F.text.startswith("/"))
async def collection_rename_submit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    collection_id = data.get("current_collection_id")
    if not collection_id:
        await state.set_state(BotStates.COLLECTIONS_LIST)
        await message.answer("Подборка не найдена.", reply_markup=main_menu_keyboard())
        return

    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз.")
        return
    if len(title) > MAX_TITLE_LEN:
        await message.answer(f"Слишком длинное название — максимум {MAX_TITLE_LEN} символов.")
        return

    runtime = build_runtime()
    async with runtime.session_factory() as session:
        renamed = await CollectionRepository(session).rename(
            str(collection_id),
            message.from_user.id,
            title,
        )
        await session.commit()
        if not renamed:
            await state.set_state(BotStates.COLLECTIONS_LIST)
            await message.answer("Подборка не найдена.", reply_markup=main_menu_keyboard())
            return
        collection = await CollectionRepository(session).get_owned(str(collection_id), message.from_user.id)
        events = await CollectionRepository(session).list_events(str(collection_id))

    assert collection is not None
    text = format_shared_collection_header(collection, events=events)
    kb = _collection_view_keyboard(str(collection_id), events).as_markup()
    await state.set_state(BotStates.COLLECTION_VIEW)
    await message.answer(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)


@router.callback_query(F.data.startswith("col:rm:"))
async def collection_remove_event(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    collection_id = parts[-2]
    try:
        index = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    loaded = await _load_owned_collection(collection_id, callback.from_user.id)
    if loaded is None:
        await callback.answer("Подборка не найдена", show_alert=True)
        return
    _collection, events = loaded
    event = _event_at_index(events, index)
    if event is None:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    runtime = build_runtime()
    async with runtime.session_factory() as session:
        removed = await CollectionRepository(session).remove_event(
            collection_id,
            callback.from_user.id,
            event.id,
        )
        await session.commit()
        if not removed:
            await callback.answer("Не удалось удалить событие", show_alert=True)
            return
        collection = await CollectionRepository(session).get_owned(collection_id, callback.from_user.id)
        events = await CollectionRepository(session).list_events(collection_id)

    assert collection is not None
    if not events:
        text = (
            f"✂️ <b>{_escape_html(collection.title)}</b>\n\n"
            "В подборке больше нет мероприятий. Добавьте события из избранного, создав новую подборку."
        )
        kb = _collection_view_keyboard(collection_id, events).as_markup()
        await state.set_state(BotStates.COLLECTION_VIEW)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
        except TelegramBadRequest:
            await callback.message.answer(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
        await callback.answer("Событие убрано")
        return

    text = (
        f"✂️ <b>{_escape_html(collection.title)}</b>\n\n"
        "Нажмите на событие, чтобы убрать его из подборки:"
    )
    kb = _collection_edit_keyboard(collection_id, events).as_markup()
    await state.set_state(BotStates.COLLECTION_EDIT)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb, parse_mode=EVENT_MESSAGE_PARSE_MODE)
    await callback.answer("Событие убрано")


@router.callback_query(F.data.startswith("col:share:"))
async def collection_share(callback: CallbackQuery) -> None:
    collection_id = callback.data.split(":")[-1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        collection = await CollectionRepository(session).get_owned(collection_id, callback.from_user.id)
    if collection is None:
        await callback.answer("Подборка не найдена", show_alert=True)
        return

    link = await build_collection_share_link(callback.bot, collection.share_token)
    await callback.message.answer(
        f"📤 Ссылка на подборку «{collection.title}»:\n\n{link}\n\n"
        "Отправьте её друзьям — они увидят список и смогут сохранить события себе.\n\n"
        f"{COLLECTION_VIEW_INSTRUCTION}",
    )
    await callback.answer("Ссылка отправлена")


@router.callback_query(F.data.startswith("col:del:"))
async def collection_delete(callback: CallbackQuery, state: FSMContext) -> None:
    collection_id = callback.data.split(":")[-1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        deleted = await CollectionRepository(session).delete(collection_id, callback.from_user.id)
        await session.commit()
    if not deleted:
        await callback.answer("Подборка не найдена", show_alert=True)
        return
    await callback.answer("Подборка удалена")
    await render_collections_index(callback, state)


@router.callback_query(F.data.startswith("col:ev:"))
async def collection_open_event(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    collection_id = parts[-2]
    try:
        index = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    loaded = await _load_owned_collection(collection_id, callback.from_user.id)
    if loaded is None:
        await callback.answer("Подборка не найдена", show_alert=True)
        return
    _collection, events = loaded
    event = _event_at_index(events, index)
    if event is None:
        await callback.answer("Событие не найдено", show_alert=True)
        return
    await show_viewing_event(callback, state, event)


@router.callback_query(F.data.startswith("sh:ev:"))
async def shared_open_event(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    share_token = parts[-2]
    try:
        index = int(parts[-1])
    except ValueError:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    runtime = build_runtime()
    async with runtime.session_factory() as session:
        col_repo = CollectionRepository(session)
        collection = await col_repo.get_by_share_token(share_token)
        if collection is None:
            await callback.answer("Подборка не найдена", show_alert=True)
            return
        events = await col_repo.list_events(collection.id)

    event = _event_at_index(events, index)
    if event is None:
        await callback.answer("Событие не найдено", show_alert=True)
        return
    await show_viewing_event(callback, state, event)


@router.callback_query(F.data.startswith("sh:save:"))
async def shared_save_all(callback: CallbackQuery) -> None:
    share_token = callback.data.split(":")[-1]
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        col_repo = CollectionRepository(session)
        collection = await col_repo.get_by_share_token(share_token)
        if collection is None:
            await callback.answer("Подборка не найдена", show_alert=True)
            return
        events = await col_repo.list_events(collection.id)
        fav_repo = FavoritesRepository(session)
        for event in events:
            await fav_repo.add(callback.from_user.id, event.id)
        await session.commit()

    await callback.answer(f"Сохранено в избранное: {len(events)}")


async def handle_share_start(message: Message, state: FSMContext, share_token: str) -> bool:
    """Returns True if deep link was handled."""
    if not share_token:
        return False
    runtime = build_runtime()
    async with runtime.session_factory() as session:
        collection = await CollectionRepository(session).get_by_share_token(share_token)
        if collection is None:
            await message.answer(
                "Подборка не найдена или была удалена.",
                reply_markup=main_menu_keyboard(),
            )
            return True
        user = await UserSettingsRepository(session).get(message.from_user.id)

    if user is None or not user.onboarding_complete:
        await state.update_data(pending_share_token=share_token)
        await state.set_state(BotStates.ONBOARDING_CITY)
        from src.bot.formatters.onboarding import welcome_city_prompt
        from src.bot.keyboards.menus import city_keyboard

        await message.answer(
            f"{COLLECTION_VIEW_INSTRUCTION}\n\n"
            "После выбора города откроем подборку друга.",
            reply_markup=city_keyboard(),
        )
        await message.answer(welcome_city_prompt())
        return True

    await show_shared_collection(message, state, share_token)
    return True
