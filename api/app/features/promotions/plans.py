from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.catalogue import Shop
from app.models.growth import Plan, Subscription


def active_subscription(db: Session, shop: Shop) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(Subscription.shop_id == shop.id, Subscription.status == "active", Subscription.ends_at > utcnow())
        .order_by(Subscription.id.desc())
    )


def plan_bps(db: Session, shop: Shop) -> int | None:
    """Commission rate from the seller's current premium plan, if they have one that sets a rate."""
    sub = active_subscription(db, shop)
    plan = db.get(Plan, sub.plan_id) if sub else None
    return plan.commission_bps if plan is not None else None
