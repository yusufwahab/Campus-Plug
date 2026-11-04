"""Sellers paying the platform for premium plans and listing boosts, through the same payment provider adapter."""

import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.payments import VerifyResult, get_provider
from app.db import utcnow
from app.features.orders import ledger
from app.features.promotions.plans import active_subscription
from app.models.catalogue import Shop
from app.models.growth import Boost, Plan, Purchase, Subscription
from app.models.identity import User
from app.notify import notify


def start(
    db: Session, *, kind: str, shop: Shop, user: User, amount_kobo: int, plan: Plan | None, boost: Boost | None, callback_url: str
) -> Purchase:
    provider = get_provider()
    reference = f"CPP-{kind.upper()}-{secrets.token_hex(5)}"
    result = provider.initialize(reference=reference, amount_kobo=amount_kobo, email=user.email, callback_url=callback_url)
    purchase = Purchase(
        kind=kind, shop_id=shop.id, plan_id=plan.id if plan else None, boost_id=boost.id if boost else None,
        amount_kobo=amount_kobo, reference=reference, provider=provider.name, checkout_url=result.checkout_url,
    )  # fmt: skip
    db.add(purchase)
    db.flush()
    return purchase


def apply(db: Session, purchase: Purchase, result: VerifyResult) -> str:
    """Idempotent: confirms the verified amount, records revenue, then activates the plan or queues the boost for approval."""
    if purchase.status == "paid":
        return "already_processed"
    if result.status != "success":
        if result.status == "failed":
            purchase.status = "failed"
        return "failed" if result.status == "failed" else "pending"
    if result.amount_kobo != purchase.amount_kobo or result.currency != "NGN":
        purchase.status = "failed"
        return "mismatch"
    purchase.status = "paid"
    ledger.post(
        db, order=None, kind=f"{purchase.kind}_purchase",
        legs=[(ledger.PROVIDER_CLEARING, purchase.amount_kobo - result.fee_kobo), (ledger.PROVIDER_FEES, result.fee_kobo), (ledger.PLATFORM_REVENUE, -purchase.amount_kobo)],
        ref=purchase.reference,
    )  # fmt: skip
    shop = db.get(Shop, purchase.shop_id)
    if purchase.kind == "plan" and purchase.plan_id is not None and shop is not None:
        plan = db.get(Plan, purchase.plan_id)
        current = active_subscription(db, shop)
        start = current.ends_at if current is not None and current.plan_id == purchase.plan_id else utcnow()
        if plan is not None:
            db.add(
                Subscription(
                    shop_id=shop.id,
                    plan_id=plan.id,
                    price_paid_kobo=purchase.amount_kobo,
                    started_at=utcnow(),
                    ends_at=start + timedelta(days=plan.period_days),
                )
            )
            if current is not None:  # a renewal or switch replaces the old row, so only one subscription stays active
                current.status = "expired" if current.plan_id == plan.id else "cancelled"
                current.cancelled_at = utcnow() if current.status == "cancelled" else None
            notify(
                db,
                shop.user_id,
                "plan.active",
                f"{plan.name} plan is active",
                "Its commission rate applies to your new orders.",
                "/seller/promotions",
            )
    elif purchase.kind == "boost" and shop is not None:
        notify(db, shop.user_id, "boost.paid", "Boost paid", "Waiting for Admin approval before it goes live.", "/seller/promotions")
    return "applied"


def refund_boost(db: Session, boost: Boost) -> None:
    """Rejecting a paid boost returns the money."""
    purchase = db.scalar(select(Purchase).where(Purchase.boost_id == boost.id, Purchase.status == "paid"))
    if purchase is None:
        return
    result = get_provider().refund(reference=purchase.reference, amount_kobo=purchase.amount_kobo)
    if result.status not in ("success", "pending"):
        raise HTTPException(502, "The refund could not be started.")
    purchase.status = "refunded"
    ledger.post(
        db,
        order=None,
        kind="boost_refund",
        legs=[(ledger.PROVIDER_CLEARING, -purchase.amount_kobo), (ledger.PLATFORM_REVENUE, purchase.amount_kobo)],
        ref=purchase.reference,
    )
