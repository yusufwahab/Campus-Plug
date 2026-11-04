from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import Shop
from app.models.commerce import Dispute, Order
from app.models.identity import User

OPEN_STATUSES = ("pending_payment", "paid", "accepted", "preparing", "ready", "delivered", "disputed")


def open_obligations(db: Session, user: User) -> str:
    """Describes what blocks account deletion ('' when nothing does): open orders or disputes on either side."""
    shop_id = db.scalar(select(Shop.id).where(Shop.user_id == user.id))
    own_orders = Order.buyer_id == user.id if shop_id is None else (Order.buyer_id == user.id) | (Order.shop_id == shop_id)
    if db.scalar(select(Order.id).where(own_orders, Order.status.in_(OPEN_STATUSES)).limit(1)) is not None:
        return "an open order"
    if (
        db.scalar(select(Dispute.id).join(Order, Order.id == Dispute.order_id).where(own_orders, Dispute.status != "resolved").limit(1))
        is not None
    ):
        return "an open dispute"
    return ""
