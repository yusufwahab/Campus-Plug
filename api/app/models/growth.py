from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class Plan(Base):
    """Premium seller plan: price, benefits and a commission rate that applies to new orders while subscribed."""

    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    price_kobo: Mapped[int] = mapped_column(Integer)
    period_days: Mapped[int] = mapped_column(Integer, default=30)
    commission_bps: Mapped[int | None] = mapped_column(Integer)
    benefits: Mapped[Any] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | cancelled | expired
    price_paid_kobo: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    note: Mapped[str] = mapped_column(Text, default="")


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), unique=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text, default="")
    confirmed_deal: Mapped[bool] = mapped_column(Boolean, default=True)
    reply: Mapped[str | None] = mapped_column(Text)
    replied_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PromoCode(Base):
    """kind: seller_buyer (seller funds a discount for buyers), admin_seller (commission discount for sellers),
    admin_buyer (platform-funded campaign: the seller still gets their normal payout)."""

    __tablename__ = "promo_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(14), index=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"), index=True)  # seller_buyer codes belong to a shop
    percent_bps: Mapped[int | None] = mapped_column(Integer)
    fixed_kobo: Mapped[int | None] = mapped_column(Integer)
    commission_bps: Mapped[int | None] = mapped_column(Integer)  # admin_seller: commission rate while the code is applied
    min_spend_kobo: Mapped[int] = mapped_column(Integer, default=0)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    used: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    listing_ids: Mapped[Any] = mapped_column(JSON, default=list)  # empty = whole shop
    category_slugs: Mapped[Any] = mapped_column(JSON, default=list)  # eligibility for platform codes
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), unique=True)
    shop_id: Mapped[int | None] = mapped_column(Integer)  # admin_seller codes applied to a shop
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Boost(Base):
    """A paid boost that raises a listing in discovery, labelled Sponsored. Admin approves and can pause it."""

    __tablename__ = "boosts"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    days: Mapped[int] = mapped_column(Integer)
    price_kobo: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending | active | paused | rejected | ended
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)  # listing_view | contact | request_response | ...
    campus_id: Mapped[int | None] = mapped_column(Integer, index=True)
    shop_id: Mapped[int | None] = mapped_column(Integer, index=True)
    listing_id: Mapped[int | None] = mapped_column(Integer)
    user_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class Purchase(Base):
    """A seller paying the platform: a premium plan or a listing boost. Goes through the same payment provider adapter."""

    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # plan | boost
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"))
    boost_id: Mapped[int | None] = mapped_column(ForeignKey("boosts.id"))
    amount_kobo: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="initiated")  # initiated | paid | failed | refunded
    reference: Mapped[str] = mapped_column(String(80), unique=True)
    provider: Mapped[str] = mapped_column(String(20))
    checkout_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
