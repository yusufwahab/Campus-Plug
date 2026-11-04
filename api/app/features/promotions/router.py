from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.adapters.payments import get_provider
from app.config import get_settings
from app.db import utcnow
from app.deps import DB, CurrentUser, SellerUser
from app.features.catalogue.seller import my_shop
from app.features.promotions import promos, purchases
from app.features.promotions.plans import active_subscription
from app.models.catalogue import Listing
from app.models.growth import Boost, Plan, PromoCode, PromoRedemption, Purchase
from app.ratelimit import rate_limit

router = APIRouter(tags=["promotions"])


# ---- buyers: preview a code -------------------------------------------------------------------------------------------


class ValidateIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    listing_id: str
    quantity: int = Field(default=1, ge=1, le=1000)


class ValidateOut(BaseModel):
    discount_kobo: int
    description: str


@router.post("/promos/validate", response_model=ValidateOut, dependencies=[Depends(rate_limit("promo-check", 30, 600))])
def validate(body: ValidateIn, user: CurrentUser, db: DB) -> ValidateOut:
    listing = db.scalar(select(Listing).where(Listing.public_id == body.listing_id.upper(), Listing.deleted_at.is_(None)))
    if listing is None:
        raise HTTPException(404, "That listing is not available.")
    result = promos.evaluate(db, user, listing, body.code, listing.price_kobo, body.quantity)
    amount = result.seller_discount_kobo or result.platform_discount_kobo
    return ValidateOut(
        discount_kobo=amount, description="Seller discount" if result.seller_discount_kobo else "Campus Plug campaign discount"
    )


# ---- seller promo codes -----------------------------------------------------------------------------------------------


class SellerPromoIn(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9]{3,20}$")
    percent: int | None = Field(default=None, ge=1, le=90)
    fixed_kobo: int | None = Field(default=None, gt=0)
    min_spend_kobo: int = Field(default=0, ge=0)
    usage_limit: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None
    listing_ids: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _one_kind(self) -> "SellerPromoIn":
        if (self.percent is None) == (self.fixed_kobo is None):
            raise ValueError("Choose either a percentage or a fixed amount")
        return self


class PromoOut(BaseModel):
    id: int
    code: str
    kind: str
    percent: int | None
    fixed_kobo: int | None
    commission_bps: int | None
    min_spend_kobo: int
    usage_limit: int | None
    used: int
    expires_at: str | None
    active: bool
    scope: str


def promo_out(p: PromoCode) -> PromoOut:
    return PromoOut(
        id=p.id,
        code=p.code,
        kind=p.kind,
        percent=p.percent_bps // 100 if p.percent_bps is not None else None,
        fixed_kobo=p.fixed_kobo,
        commission_bps=p.commission_bps,
        min_spend_kobo=p.min_spend_kobo,
        usage_limit=p.usage_limit,
        used=p.used,
        expires_at=p.expires_at.isoformat() if p.expires_at else None,
        active=p.active,
        scope="Chosen items"
        if p.listing_ids
        else "Whole shop"
        if p.kind == "seller_buyer"
        else ", ".join(p.category_slugs or []) or "Everything",
    )


@router.post("/seller/promos", response_model=PromoOut, status_code=201)
def create_seller_promo(body: SellerPromoIn, user: SellerUser, db: DB) -> PromoOut:
    shop = my_shop(db, user)
    code = body.code.upper()
    if db.scalar(select(PromoCode.id).where(PromoCode.code == code)):
        raise HTTPException(409, "That code is already taken.")
    if body.expires_at is not None and body.expires_at <= utcnow():
        raise HTTPException(422, "The expiry must be in the future.")
    ids: list[int] = []
    for public_id in body.listing_ids:
        listing = db.scalar(select(Listing).where(Listing.public_id == public_id.upper(), Listing.shop_id == shop.id))
        if listing is None:
            raise HTTPException(422, f"{public_id} is not one of your listings.")
        ids.append(listing.id)
    promo = PromoCode(
        code=code, kind="seller_buyer", shop_id=shop.id, percent_bps=body.percent * 100 if body.percent else None, fixed_kobo=body.fixed_kobo,
        min_spend_kobo=body.min_spend_kobo, usage_limit=body.usage_limit, expires_at=body.expires_at, listing_ids=ids, created_by=user.id,
    )  # fmt: skip
    db.add(promo)
    db.commit()
    return promo_out(promo)


class AppliedOut(BaseModel):
    code: str
    commission_bps: int | None
    applied_at: str


class SellerPromos(BaseModel):
    codes: list[PromoOut]
    applied_admin_codes: list[AppliedOut]


@router.get("/seller/promos", response_model=SellerPromos)
def my_promos(user: SellerUser, db: DB) -> SellerPromos:
    shop = my_shop(db, user)
    codes = db.scalars(select(PromoCode).where(PromoCode.shop_id == shop.id).order_by(PromoCode.id.desc()))
    applied = db.execute(
        select(PromoRedemption, PromoCode)
        .join(PromoCode, PromoCode.id == PromoRedemption.promo_id)
        .where(PromoRedemption.shop_id == shop.id, PromoCode.kind == "admin_seller")
    )
    return SellerPromos(
        codes=[promo_out(c) for c in codes],
        applied_admin_codes=[
            AppliedOut(code=p.code, commission_bps=p.commission_bps, applied_at=r.created_at.isoformat()) for r, p in applied
        ],
    )


@router.post("/seller/promos/{promo_id}/active", response_model=PromoOut)
def toggle_promo(promo_id: int, active: bool, user: SellerUser, db: DB) -> PromoOut:
    shop = my_shop(db, user)
    promo = db.get(PromoCode, promo_id)
    if promo is None or promo.shop_id != shop.id:
        raise HTTPException(404, "Code not found.")
    promo.active = active
    db.commit()
    return promo_out(promo)


class ApplyIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)


@router.post("/seller/promos/apply", response_model=SellerPromos)
def apply_admin_code(body: ApplyIn, user: SellerUser, db: DB) -> SellerPromos:
    """Applies an Admin commission discount code to this shop. The lower rate affects new orders only."""
    shop = my_shop(db, user)
    promo = db.scalar(select(PromoCode).where(PromoCode.code == body.code.strip().upper(), PromoCode.kind == "admin_seller"))
    if promo is None or not promo.active or (promo.expires_at is not None and promo.expires_at <= utcnow()):
        raise HTTPException(422, "That code is not valid.")
    if promo.usage_limit is not None and promo.used >= promo.usage_limit:
        raise HTTPException(422, "That code has been fully used.")
    if db.scalar(select(PromoRedemption.id).where(PromoRedemption.promo_id == promo.id, PromoRedemption.shop_id == shop.id)):
        raise HTTPException(409, "You already applied this code.")
    promo.used += 1
    db.add(PromoRedemption(promo_id=promo.id, shop_id=shop.id, user_id=user.id))
    if promo.commission_bps is not None:
        shop.commission_override_bps = promo.commission_bps
    db.commit()
    return my_promos(user, db)


# ---- premium plans ----------------------------------------------------------------------------------------------------


class PlanOut(BaseModel):
    id: int
    name: str
    price_kobo: int
    period_days: int
    commission_bps: int | None
    benefits: list[str]


class PlansOut(BaseModel):
    plans: list[PlanOut]
    current_plan: str | None
    current_ends_at: str | None


class PayStart(BaseModel):
    checkout_url: str
    reference: str


def _callback() -> str:
    return f"{get_settings().web_url}/seller/promotions?purchase=done"


@router.get("/plans", response_model=PlansOut)
def list_plans(user: SellerUser, db: DB) -> PlansOut:
    shop = my_shop(db, user)
    sub = active_subscription(db, shop)
    current = db.get(Plan, sub.plan_id) if sub else None
    plans = db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.price_kobo))
    return PlansOut(
        plans=[
            PlanOut(
                id=p.id,
                name=p.name,
                price_kobo=p.price_kobo,
                period_days=p.period_days,
                commission_bps=p.commission_bps,
                benefits=list(p.benefits or []),
            )
            for p in plans
        ],
        current_plan=current.name if current else None,
        current_ends_at=sub.ends_at.isoformat() if sub else None,
    )


class BuyPlanIn(BaseModel):
    plan_id: int


@router.post("/seller/plan/buy", response_model=PayStart, dependencies=[Depends(rate_limit("purchase", 10, 3600))])
def buy_plan(body: BuyPlanIn, user: SellerUser, db: DB) -> PayStart:
    """Buying or renewing a premium plan. Only verified sellers can subscribe."""
    shop = my_shop(db, user)
    plan = db.get(Plan, body.plan_id)
    if plan is None or not plan.active:
        raise HTTPException(404, "That plan is not available.")
    if shop.verification_status != "verified":
        raise HTTPException(403, "Verify your identity before buying a plan.")
    purchase = purchases.start(
        db, kind="plan", shop=shop, user=user, amount_kobo=plan.price_kobo, plan=plan, boost=None, callback_url=_callback()
    )
    db.commit()
    return PayStart(checkout_url=purchase.checkout_url, reference=purchase.reference)


@router.post("/seller/plan/cancel", response_model=PlansOut)
def cancel_plan(user: SellerUser, db: DB) -> PlansOut:
    """Cancelling stops renewal and ends the plan's commission rate now; nothing is refunded."""
    shop = my_shop(db, user)
    sub = active_subscription(db, shop)
    if sub is None:
        raise HTTPException(409, "You have no active plan.")
    sub.status, sub.cancelled_at = "cancelled", utcnow()
    db.commit()
    return list_plans(user, db)


# ---- boosts -----------------------------------------------------------------------------------------------------------


BOOST_PER_DAY_KOBO = 50_000


class BoostIn(BaseModel):
    listing_id: str
    days: Literal[3, 7, 14]


class BoostOut(BaseModel):
    id: int
    listing_id: str
    days: int
    price_kobo: int
    status: str
    ends_at: str | None


def boost_out(db: DB, b: Boost) -> BoostOut:
    listing = db.get(Listing, b.listing_id)
    return BoostOut(
        id=b.id,
        listing_id=listing.public_id if listing else "",
        days=b.days,
        price_kobo=b.price_kobo,
        status=b.status,
        ends_at=b.ends_at.isoformat() if b.ends_at else None,
    )


@router.post("/seller/boosts", response_model=PayStart, status_code=201, dependencies=[Depends(rate_limit("purchase", 10, 3600))])
def buy_boost(body: BoostIn, user: SellerUser, db: DB) -> PayStart:
    shop = my_shop(db, user)
    listing = db.scalar(
        select(Listing).where(Listing.public_id == body.listing_id.upper(), Listing.shop_id == shop.id, Listing.status == "active")
    )
    if listing is None:
        raise HTTPException(404, "Choose one of your live listings.")
    price = BOOST_PER_DAY_KOBO * body.days
    boost = Boost(listing_id=listing.id, shop_id=shop.id, days=body.days, price_kobo=price)
    db.add(boost)
    db.flush()
    purchase = purchases.start(db, kind="boost", shop=shop, user=user, amount_kobo=price, plan=None, boost=boost, callback_url=_callback())
    db.commit()
    return PayStart(checkout_url=purchase.checkout_url, reference=purchase.reference)


@router.get("/seller/boosts", response_model=list[BoostOut])
def my_boosts(user: SellerUser, db: DB) -> list[BoostOut]:
    shop = my_shop(db, user)
    return [boost_out(db, b) for b in db.scalars(select(Boost).where(Boost.shop_id == shop.id).order_by(Boost.id.desc())) if _paid(db, b)]


def _paid(db: DB, b: Boost) -> bool:
    return db.scalar(select(Purchase.id).where(Purchase.boost_id == b.id, Purchase.status.in_(("paid", "refunded")))) is not None


@router.get("/seller/purchases/{reference}/status")
def purchase_status(reference: str, user: SellerUser, db: DB) -> dict[str, str]:
    """Verifies a plan or boost payment when the seller returns from checkout. Safe to call repeatedly."""
    shop = my_shop(db, user)
    purchase = db.scalar(select(Purchase).where(Purchase.reference == reference, Purchase.shop_id == shop.id))
    if purchase is None:
        raise HTTPException(404, "Purchase not found.")
    if purchase.status == "initiated":
        outcome = purchases.apply(db, purchase, get_provider().verify(purchase.reference))
        db.commit()
        return {"status": outcome}
    return {"status": purchase.status}


def boost_end_time(days: int) -> datetime:
    return utcnow() + timedelta(days=days)
