from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow

ORDER_STATUSES = (
    "pending_payment",
    "paid",
    "accepted",
    "preparing",
    "ready",
    "delivered",
    "confirmed",
    "paid_out",
    "cancelled",
    "refunded",
    "disputed",
)


class Order(Base):
    """An order stores its own price, discounts, commission rate and amounts permanently: later rate changes never touch it."""

    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(20), unique=True)  # CP-O-n
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    request_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending_payment", index=True)
    listing_title: Mapped[str] = mapped_column(String(140))
    listing_type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_kobo: Mapped[int] = mapped_column(Integer)
    seller_discount_kobo: Mapped[int] = mapped_column(Integer, default=0)
    platform_discount_kobo: Mapped[int] = mapped_column(Integer, default=0)
    item_paid_kobo: Mapped[int] = mapped_column(Integer)
    delivery_fee_kobo: Mapped[int] = mapped_column(Integer, default=0)
    buyer_total_kobo: Mapped[int] = mapped_column(Integer)
    commission_bps: Mapped[int] = mapped_column(Integer)
    commission_kobo: Mapped[int] = mapped_column(Integer)
    seller_amount_kobo: Mapped[int] = mapped_column(Integer)
    provider_fee_kobo: Mapped[int] = mapped_column(Integer, default=0)
    provider_fee_absorbed: Mapped[bool] = mapped_column(Boolean, default=True)
    refunded_item_kobo: Mapped[int] = mapped_column(Integer, default=0)
    commission_returned_kobo: Mapped[int] = mapped_column(Integer, default=0)
    protected: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_method: Mapped[str] = mapped_column(String(10), default="app")  # app | offline
    instant_split: Mapped[bool] = mapped_column(Boolean, default=False)
    funds_released: Mapped[bool] = mapped_column(Boolean, default=False)
    fulfilment: Mapped[str] = mapped_column(String(10), default="pickup")
    booking_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    deposit_only: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(300), default="")
    promo_code_id: Mapped[int | None] = mapped_column(Integer)
    offline_confirmed_by: Mapped[Any] = mapped_column(JSON, default=list)
    cancel_reason: Mapped[str] = mapped_column(String(300), default="")
    accept_by: Mapped[datetime | None] = mapped_column(UTCDateTime())
    auto_confirm_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class OrderEvent(Base):
    """Append-only history of every status change."""

    __tablename__ = "order_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="initiated")  # initiated | success | failed | refunded
    amount_kobo: Mapped[int] = mapped_column(Integer)
    fee_kobo: Mapped[int] = mapped_column(Integer, default=0)
    checkout_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class WebhookEvent(Base):
    """Remembers every webhook already processed, so a provider sending the same event twice changes nothing."""

    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    event_key: Mapped[str] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(40), default="processed")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class LedgerEntry(Base):
    """Append-only money ledger. Every movement is a group of legs that sum to zero; nothing is ever updated or deleted."""

    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[str] = mapped_column(String(40), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    account: Mapped[str] = mapped_column(String(30), index=True)
    amount_kobo: Mapped[int] = mapped_column(Integer)
    ref: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Payout(Base):
    __tablename__ = "payouts"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    amount_kobo: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending | held | processing | paid | failed
    hold_reason: Mapped[str] = mapped_column(String(200), default="")
    provider_ref: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    amount_kobo: Mapped[int] = mapped_column(Integer)
    commission_returned_kobo: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | done | failed
    provider_ref: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Dispute(Base):
    __tablename__ = "disputes"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(20), unique=True)  # CP-D-n
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="awaiting_seller", index=True)  # awaiting_seller | under_review | resolved
    seller_response: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[Any] = mapped_column(JSON, default=list)
    response_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolution: Mapped[str] = mapped_column(String(20), default="")  # full_refund | partial_refund | release
    refund_item_kobo: Mapped[int] = mapped_column(Integer, default=0)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    admin_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
