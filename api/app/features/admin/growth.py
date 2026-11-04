from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.audit import log_admin_action
from app.db import utcnow
from app.deps import DB, AdminUser
from app.features.promotions import purchases
from app.features.promotions.router import PromoOut, boost_out, promo_out
from app.models.catalogue import Shop
from app.models.growth import Boost, Plan, PromoCode, Purchase
from app.notify import notify

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminPromoIn(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9]{3,20}$")
    kind: Literal["admin_seller", "admin_buyer"]
    percent: int | None = Field(default=None, ge=1, le=90)
    fixed_kobo: int | None = Field(default=None, gt=0)
    commission_bps: int | None = Field(default=None, ge=0, le=10_000)
    min_spend_kobo: int = Field(default=0, ge=0)
    usage_limit: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None
    category_slugs: list[str] = Field(default_factory=list, max_length=8)
    reason: str = Field(min_length=3)

    @model_validator(mode="after")
    def _shape(self) -> "AdminPromoIn":
        if self.kind == "admin_seller" and self.commission_bps is None:
            raise ValueError("A seller code needs a commission rate")
        if self.kind == "admin_buyer" and (self.percent is None) == (self.fixed_kobo is None):
            raise ValueError("A buyer campaign code needs either a percentage or a fixed amount")
        return self


@router.get("/promos", response_model=list[PromoOut])
def promos(admin: AdminUser, db: DB) -> list[PromoOut]:
    return [promo_out(p) for p in db.scalars(select(PromoCode).where(PromoCode.kind != "seller_buyer").order_by(PromoCode.id.desc()))]


@router.post("/promos", response_model=PromoOut, status_code=201)
def create_promo(body: AdminPromoIn, admin: AdminUser, db: DB) -> PromoOut:
    code = body.code.upper()
    if db.scalar(select(PromoCode.id).where(PromoCode.code == code)):
        raise HTTPException(409, "That code is already taken.")
    promo = PromoCode(
        code=code, kind=body.kind, percent_bps=body.percent * 100 if body.percent else None, fixed_kobo=body.fixed_kobo, commission_bps=body.commission_bps,
        min_spend_kobo=body.min_spend_kobo, usage_limit=body.usage_limit, expires_at=body.expires_at, category_slugs=body.category_slugs, created_by=admin.id,
    )  # fmt: skip
    db.add(promo)
    log_admin_action(db, admin, "promo.created", "promo", code, reason=body.reason, after=body.model_dump(mode="json", exclude={"reason"}))
    db.commit()
    return promo_out(promo)


class ToggleIn(BaseModel):
    active: bool
    reason: str = Field(min_length=3)


@router.post("/promos/{promo_id}/active", response_model=PromoOut)
def toggle_promo(promo_id: int, body: ToggleIn, admin: AdminUser, db: DB) -> PromoOut:
    promo = db.get(PromoCode, promo_id)
    if promo is None:
        raise HTTPException(404, "Code not found.")
    log_admin_action(db, admin, "promo.active" if body.active else "promo.deactivated", "promo", promo.code, reason=body.reason)
    promo.active = body.active
    db.commit()
    return promo_out(promo)


# ---- plans ------------------------------------------------------------------------------------------------------------


class PlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    price_kobo: int = Field(gt=0, le=100_000_000)
    period_days: int = Field(default=30, ge=1, le=365)
    commission_bps: int | None = Field(default=None, ge=0, le=10_000)
    benefits: list[str] = Field(default_factory=list, max_length=10)
    active: bool = True
    reason: str = Field(min_length=3)


class PlanAdmin(BaseModel):
    id: int
    name: str
    price_kobo: int
    period_days: int
    commission_bps: int | None
    benefits: list[str]
    active: bool


def _plan(p: Plan) -> PlanAdmin:
    return PlanAdmin(
        id=p.id,
        name=p.name,
        price_kobo=p.price_kobo,
        period_days=p.period_days,
        commission_bps=p.commission_bps,
        benefits=list(p.benefits or []),
        active=p.active,
    )


@router.get("/plans", response_model=list[PlanAdmin])
def list_plans(admin: AdminUser, db: DB) -> list[PlanAdmin]:
    return [_plan(p) for p in db.scalars(select(Plan).order_by(Plan.price_kobo))]


@router.post("/plans", response_model=PlanAdmin, status_code=201)
def create_plan(body: PlanIn, admin: AdminUser, db: DB) -> PlanAdmin:
    if db.scalar(select(Plan.id).where(Plan.name == body.name)):
        raise HTTPException(409, "A plan with that name exists.")
    plan = Plan(**body.model_dump(exclude={"reason"}))
    db.add(plan)
    log_admin_action(db, admin, "plan.created", "plan", body.name, reason=body.reason, after=body.model_dump(exclude={"reason"}))
    db.commit()
    return _plan(plan)


@router.put("/plans/{plan_id}", response_model=PlanAdmin)
def update_plan(plan_id: int, body: PlanIn, admin: AdminUser, db: DB) -> PlanAdmin:
    """Price and rate changes apply to new purchases and new orders; current subscribers keep what they paid for."""
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found.")
    log_admin_action(
        db,
        admin,
        "plan.updated",
        "plan",
        plan.name,
        reason=body.reason,
        before=_plan(plan).model_dump(),
        after=body.model_dump(exclude={"reason"}),
    )
    for key, value in body.model_dump(exclude={"reason"}).items():
        setattr(plan, key, value)
    db.commit()
    return _plan(plan)


# ---- sponsored placement (boosts) --------------------------------------------------------------------------------------


class SponsoredAction(BaseModel):
    action: Literal["approve", "reject", "pause", "resume"]
    reason: str = Field(min_length=3)


@router.get("/sponsored", response_model=list[dict])
def sponsored(admin: AdminUser, db: DB, status: str = "") -> list[dict]:
    query = select(Boost, Purchase).join(Purchase, Purchase.boost_id == Boost.id).where(Purchase.status.in_(("paid", "refunded")))
    if status:
        query = query.where(Boost.status == status)
    out = []
    for boost, purchase in db.execute(query.order_by(Boost.id.desc()).limit(100)):
        shop = db.get(Shop, boost.shop_id)
        out.append({**boost_out(db, boost).model_dump(), "shop_name": shop.name if shop else "", "payment": purchase.status})
    return out


@router.post("/sponsored/{boost_id}/action", response_model=dict)
def sponsored_action(boost_id: int, body: SponsoredAction, admin: AdminUser, db: DB) -> dict:
    boost = db.get(Boost, boost_id)
    if boost is None or db.scalar(select(Purchase.id).where(Purchase.boost_id == boost.id, Purchase.status == "paid")) is None:
        raise HTTPException(404, "Boost not found.")
    shop = db.get(Shop, boost.shop_id)
    log_admin_action(db, admin, f"boost.{body.action}", "boost", boost.id, reason=body.reason, before={"status": boost.status})
    if body.action == "approve" and boost.status == "pending":
        boost.status, boost.starts_at, boost.ends_at = "active", utcnow(), utcnow() + timedelta(days=boost.days)
    elif body.action == "reject" and boost.status in ("pending", "active", "paused"):
        boost.status = "rejected"
        purchases.refund_boost(db, boost)
    elif body.action == "pause" and boost.status == "active":
        boost.status = "paused"
    elif body.action == "resume" and boost.status == "paused":
        boost.status = "active"
    else:
        raise HTTPException(409, f"A {boost.status} boost cannot be {body.action}d.")
    if shop is not None:
        notify(db, shop.user_id, "boost.update", f"Your boost was {boost.status}", body.reason, "/seller/promotions")
    db.commit()
    return boost_out(db, boost).model_dump()
