from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.catalogue import Category, Listing, Shop
from app.models.commerce import Order
from app.models.growth import PromoCode, PromoRedemption
from app.models.identity import User
from app.settings_store import get_setting


@dataclass(frozen=True)
class PromoResult:
    promo: PromoCode
    seller_discount_kobo: int
    platform_discount_kobo: int


def _price_was_raised_recently(db: Session, listing: Listing) -> bool:
    """Flags discounts on listings whose price was pushed up shortly before the discount: the price rise cancels the saving."""
    if listing.previous_price_kobo is None or listing.price_changed_at is None:
        return False
    if listing.price_changed_at < utcnow() - timedelta(days=7):
        return False
    limit = get_setting(db, "listing_price_spike_pct")
    return listing.price_kobo * 100 > listing.previous_price_kobo * (100 + limit)


def evaluate(db: Session, user: User, listing: Listing, code: str, unit_price_kobo: int, quantity: int) -> PromoResult:
    promo = db.scalar(select(PromoCode).where(PromoCode.code == code.strip().upper()))
    if promo is None or not promo.active or promo.kind not in ("seller_buyer", "admin_buyer"):
        raise HTTPException(422, "That promo code is not valid.")
    now = utcnow()
    if promo.expires_at is not None and promo.expires_at <= now:
        raise HTTPException(422, "That promo code has expired.")
    if promo.usage_limit is not None and promo.used >= promo.usage_limit:
        raise HTTPException(422, "That promo code has been fully used.")
    shop = db.get(Shop, listing.shop_id)
    if shop is None:
        raise HTTPException(404, "That listing is not available.")
    if promo.kind == "seller_buyer":
        if promo.shop_id != listing.shop_id:
            raise HTTPException(422, "That code is for a different shop.")
        owner = db.get(Shop, promo.shop_id)
        if owner is not None and owner.user_id == user.id:
            raise HTTPException(422, "Sellers cannot use their own codes.")
        if promo.listing_ids and listing.id not in promo.listing_ids:
            raise HTTPException(422, "That code does not apply to this item.")
    else:
        slugs = promo.category_slugs or []
        cat = db.get(Category, listing.category_id)
        if slugs and (cat is None or cat.slug not in slugs):
            raise HTTPException(422, "That code does not apply to this category.")
        if shop.user_id == user.id:
            raise HTTPException(422, "You cannot use a code on your own listing.")
    gross = unit_price_kobo * quantity
    if gross < promo.min_spend_kobo:
        raise HTTPException(422, f"Spend at least ₦{promo.min_spend_kobo // 100:,} to use this code.")
    if _price_was_raised_recently(db, listing):
        raise HTTPException(422, "This listing's price was raised recently, so the discount cannot be applied.")
    amount = gross * promo.percent_bps // 10_000 if promo.percent_bps is not None else (promo.fixed_kobo or 0)
    amount = min(amount, gross)
    if amount <= 0:
        raise HTTPException(422, "That promo code gives no discount here.")
    if promo.kind == "seller_buyer":
        return PromoResult(promo, seller_discount_kobo=amount, platform_discount_kobo=0)
    return PromoResult(promo, seller_discount_kobo=0, platform_discount_kobo=amount)


def price_with_promo(db: Session, user: User, listing: Listing, code: str, unit_price_kobo: int, quantity: int) -> dict[str, Any]:
    """Keyword arguments for create_order. Seller codes lower the price the commission is charged on;
    platform campaign codes are paid by Campus Plug, so the seller's payout is unchanged."""
    result = evaluate(db, user, listing, code, unit_price_kobo, quantity)
    return {
        "seller_discount_kobo": result.seller_discount_kobo,
        "platform_discount_kobo": result.platform_discount_kobo,
        "promo_code_id": result.promo.id,
    }


def redeem(db: Session, order: Order, user: User) -> None:
    if order.promo_code_id is None:
        return
    promo = db.get(PromoCode, order.promo_code_id)
    if promo is not None:
        promo.used += 1
        db.add(PromoRedemption(promo_id=promo.id, order_id=order.id, user_id=user.id))


def release(db: Session, order: Order) -> None:
    """An order cancelled before payment gives its code use back."""
    if order.promo_code_id is None:
        return
    promo = db.get(PromoCode, order.promo_code_id)
    redemption = db.scalar(select(PromoRedemption).where(PromoRedemption.order_id == order.id))
    if promo is not None and redemption is not None and order.paid_at is None:
        promo.used = max(promo.used - 1, 0)
        db.delete(redemption)
