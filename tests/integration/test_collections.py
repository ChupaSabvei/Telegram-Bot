from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.storage.repositories.collections import CollectionRepository, MAX_ITEMS_PER_COLLECTION
from src.storage.repositories.events import EventRepository
from src.storage.repositories.favorites import FavoritesRepository
from src.storage.schemas import EventDTO


async def _seed_event(repo: EventRepository, *, url: str, title: str) -> str:
    event = await repo.upsert_event(
        EventDTO(
            source_url=url,
            source_slug="kudago",
            title=title,
            category_slug="concerts",
            activity_slug="culture",
            city_slug="moscow",
            start_at=datetime.now(tz=UTC) + timedelta(days=5),
            venue_format="indoor",
        )
    )
    return event.id


@pytest.mark.asyncio
async def test_collection_create_add_and_list_events(db_runtime) -> None:
    owner_id = 700001
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        col_repo = CollectionRepository(session)
        id1 = await _seed_event(repo, url="https://example.com/col/1", title="Концерт A")
        id2 = await _seed_event(repo, url="https://example.com/col/2", title="Концерт B")
        await session.commit()

        collection = await col_repo.create(owner_id, "На выходные")
        added = await col_repo.add_events(collection.id, [id1, id2])
        await session.commit()

        events = await col_repo.list_events(collection.id)
        collections = await col_repo.list_for_owner(owner_id)

    assert added == 2
    assert len(events) == 2
    assert events[0].title == "Концерт A"
    assert len(collections) == 1
    assert collections[0].share_token


@pytest.mark.asyncio
async def test_collection_get_by_share_token(db_runtime) -> None:
    owner_id = 700002
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        col_repo = CollectionRepository(session)
        event_id = await _seed_event(repo, url="https://example.com/col/3", title="Театр")
        await session.commit()

        collection = await col_repo.create(owner_id, "С другом")
        await col_repo.add_events(collection.id, [event_id])
        await session.commit()
        token = collection.share_token

        loaded = await col_repo.get_by_share_token(token)

    assert loaded is not None
    assert loaded.id == collection.id
    assert loaded.title == "С другом"


@pytest.mark.asyncio
async def test_collection_respects_item_limit(db_runtime) -> None:
    owner_id = 700003
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        col_repo = CollectionRepository(session)
        ids = []
        for idx in range(MAX_ITEMS_PER_COLLECTION + 3):
            ids.append(
                await _seed_event(
                    repo,
                    url=f"https://example.com/col/limit/{idx}",
                    title=f"Event {idx}",
                )
            )
        await session.commit()

        collection = await col_repo.create(owner_id, "Лимит")
        added = await col_repo.add_events(collection.id, ids)
        await session.commit()
        events = await col_repo.list_events(collection.id)

    assert added == MAX_ITEMS_PER_COLLECTION
    assert len(events) == MAX_ITEMS_PER_COLLECTION


@pytest.mark.asyncio
async def test_collection_rename(db_runtime) -> None:
    owner_id = 700006
    async with db_runtime.session_factory() as session:
        col_repo = CollectionRepository(session)
        collection = await col_repo.create(owner_id, "Старое название")
        await session.commit()

        renamed = await col_repo.rename(collection.id, owner_id, "  Новое название  ")
        await session.commit()
        loaded = await col_repo.get_owned(collection.id, owner_id)

    assert renamed is True
    assert loaded is not None
    assert loaded.title == "Новое название"


@pytest.mark.asyncio
async def test_collection_remove_event(db_runtime) -> None:
    owner_id = 700007
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        col_repo = CollectionRepository(session)
        id1 = await _seed_event(repo, url="https://example.com/col/rm/1", title="Keep")
        id2 = await _seed_event(repo, url="https://example.com/col/rm/2", title="Remove")
        await session.commit()

        collection = await col_repo.create(owner_id, "Edit me")
        await col_repo.add_events(collection.id, [id1, id2])
        await session.commit()

        removed = await col_repo.remove_event(collection.id, owner_id, id2)
        await session.commit()
        events = await col_repo.list_events(collection.id)

    assert removed is True
    assert len(events) == 1
    assert events[0].id == id1


@pytest.mark.asyncio
async def test_shared_collection_save_to_favorites(db_runtime) -> None:
    owner_id = 700004
    viewer_id = 700005
    async with db_runtime.session_factory() as session:
        repo = EventRepository(session)
        col_repo = CollectionRepository(session)
        fav_repo = FavoritesRepository(session)
        event_id = await _seed_event(repo, url="https://example.com/col/4", title="Shared")
        await session.commit()

        collection = await col_repo.create(owner_id, "Share me")
        await col_repo.add_events(collection.id, [event_id])
        await session.commit()

        events = await col_repo.list_events(collection.id)
        for event in events:
            await fav_repo.add(viewer_id, event.id)
        await session.commit()

        saved = await fav_repo.list_for_user(viewer_id)

    assert len(saved) == 1
    assert saved[0].id == event_id
