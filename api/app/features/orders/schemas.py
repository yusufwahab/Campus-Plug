from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    listing_id: str | None = None  # CP-P-n / CP-S-n for a direct "Buy" or "Book"
    message_id: int | None = None  # a payment request message in chat
    quantity: int = Field(default=1, ge=1, le=1000)
    fulfilment: Literal["pickup", "delivery"] = "pickup"
    booking_at: datetime | None = None
    note: str = Field(default="", max_length=300)
    promo_code: str | None = Field(default=None, max_length=40)


class OfflineDealIn(BaseModel):
    conversation_id: int
    agreed_price_kobo: int = Field(gt=0, le=100_000_000)
    quantity: int = Field(default=1, ge=1, le=1000)
    note: str = Field(default="", max_length=300)


class CancelIn(BaseModel):
    reason: str = Field(default="", max_length=300)


class StageIn(BaseModel):
    stage: Literal["preparing", "ready", "delivered"]


class ProblemIn(BaseModel):
    reason: Literal["not_received", "not_as_described", "damaged", "wrong_item", "no_show", "other"]
    details: str = Field(default="", max_length=2000)


class RespondIn(BaseModel):
    message: str = Field(min_length=3, max_length=2000)


class PayOut(BaseModel):
    checkout_url: str
    reference: str
    provider: str


class EventOut(BaseModel):
    status: str
    note: str
    at: str


class DisputeOut(BaseModel):
    public_id: str
    status: str
    reason: str
    details: str
    seller_response: str
    resolution: str
    refund_item_kobo: int
    admin_note: str
    response_due_at: str | None
    evidence: list[dict]
    opened_by_me: bool


class OrderOut(BaseModel):
    public_id: str
    status: str
    role: Literal["buyer", "seller", "admin"]
    listing_id: str
    listing_title: str
    listing_type: str
    quantity: int
    unit_price_kobo: int
    seller_discount_kobo: int
    platform_discount_kobo: int
    item_paid_kobo: int
    delivery_fee_kobo: int
    buyer_total_kobo: int
    fulfilment: str
    booking_at: str | None
    deposit_only: bool
    protected: bool
    payment_method: str
    note: str
    conversation_id: int | None
    other_party: str
    other_phone: str | None
    created_at: str
    paid_at: str | None
    accept_by: str | None
    auto_confirm_at: str | None
    cancel_reason: str
    refunded_item_kobo: int
    actions: list[str]
    timeline: list[EventOut]
    dispute: DisputeOut | None
    can_review: bool
    # seller / admin only (never shown to buyers)
    commission_bps: int | None = None
    commission_kobo: int | None = None
    seller_amount_kobo: int | None = None
    provider_fee_kobo: int | None = None
    payout_status: str | None = None


class EarningsOut(BaseModel):
    gross_sales_kobo: int
    discounts_kobo: int
    commission_kobo: int
    net_earnings_kobo: int
    held_kobo: int
    processing_payouts_kobo: int
    paid_payouts_kobo: int
    unverified: bool
    payout_review_required: bool
    payouts: list[dict]
