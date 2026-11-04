from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow

LISTING_STATUSES = ("draft", "active", "paused", "sold_out", "expired", "removed")


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    tint: Mapped[str] = mapped_column(String(12), default="mint")
    position: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    commission_override_bps: Mapped[int | None] = mapped_column(Integer)


class Shop(Base):
    __tablename__ = "shops"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(20), unique=True)  # CP-SL-n
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str] = mapped_column(Text, default="")
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    vendor_type: Mapped[str] = mapped_column(String(10), default="student")
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    trust_level: Mapped[str] = mapped_column(String(20), default="phone_confirmed")
    holiday_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    rules_accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    payout_bank: Mapped[str | None] = mapped_column(String(60))
    payout_account_number: Mapped[str | None] = mapped_column(String(20))
    payout_account_name: Mapped[str | None] = mapped_column(String(120))
    payout_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    commission_override_bps: Mapped[int | None] = mapped_column(Integer)
    plan_id: Mapped[int | None] = mapped_column(Integer)
    confirmed_deals: Mapped[int] = mapped_column(Integer, default=0)
    rating_sum: Mapped[int] = mapped_column(Integer, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    unconfirmed_sum: Mapped[int] = mapped_column(Integer, default=0)
    unconfirmed_count: Mapped[int] = mapped_column(Integer, default=0)
    shared_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    onboarded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(20), unique=True)  # CP-P-n / CP-S-n
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    type: Mapped[str] = mapped_column(String(10), index=True)  # product | service
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text, default="")
    price_kobo: Mapped[int] = mapped_column(Integer)
    price_max_kobo: Mapped[int | None] = mapped_column(Integer)
    negotiable: Mapped[bool] = mapped_column(Boolean, default=False)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)
    condition: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    variants: Mapped[Any] = mapped_column(JSON, default=list)
    fulfilment: Mapped[str] = mapped_column(String(20), default="pickup")  # pickup | delivery | both
    delivery_fee_kobo: Mapped[int] = mapped_column(Integer, default=0)
    preorder: Mapped[bool] = mapped_column(Boolean, default=False)
    availability: Mapped[str | None] = mapped_column(String(200))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    deposit_kobo: Mapped[int | None] = mapped_column(Integer)
    packages: Mapped[Any] = mapped_column(JSON, default=list)
    open_now: Mapped[bool] = mapped_column(Boolean, default=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    previous_price_kobo: Mapped[int | None] = mapped_column(Integer)
    price_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ListingImage(Base):
    __tablename__ = "listing_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    path: Mapped[str] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(Integer, default=0)


class SavedItem(Base):
    __tablename__ = "saved_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))


class SearchLog(Base):
    __tablename__ = "search_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    query: Mapped[str] = mapped_column(String(200), index=True)
    results: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
