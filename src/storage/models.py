from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    description_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False)

    events: Mapped[list[Event]] = relationship(back_populates="category")


class EventSource(Base):
    __tablename__ = "event_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="aggregator", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    events: Mapped[list[Event]] = relationship(back_populates="source")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_events_source_url"),
        Index("ix_events_city_category_start", "city_slug", "category_id", "start_at"),
        Index("ix_events_dedup_group_id", "dedup_group_id"),
        Index("ix_events_city_activity_start", "city_slug", "activity_slug", "start_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(ForeignKey("event_sources.id"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    dedup_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
    activity_slug: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    start_at_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    session_starts_at: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    price_type: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    price_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    price_amount_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue_format: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    audience_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    popularity_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    source: Mapped[EventSource] = relationship(back_populates="events")
    category: Mapped[Category] = relationship(back_populates="events")
    favorites: Mapped[list[Favorite]] = relationship(back_populates="event", cascade="all, delete-orphan")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("telegram_id", "event_id", name="uq_favorites_user_event"),
        Index("ix_favorites_telegram_saved", "telegram_id", "saved_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    event: Mapped[Event] = relationship(back_populates="favorites")


class EventCollection(Base):
    __tablename__ = "event_collections"
    __table_args__ = (
        UniqueConstraint("share_token", name="uq_event_collections_share_token"),
        Index("ix_event_collections_owner_updated", "owner_telegram_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    share_token: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    items: Mapped[list[CollectionItem]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="CollectionItem.sort_order",
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "event_id", name="uq_collection_items_collection_event"),
        Index("ix_collection_items_collection_sort", "collection_id", "sort_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("event_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    collection: Mapped[EventCollection] = relationship(back_populates="items")
    event: Mapped[Event] = relationship()


class UserSettings(Base):
    __tablename__ = "user_settings"

    telegram_id: Mapped[int] = mapped_column(primary_key=True)
    city_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
