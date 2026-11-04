from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_admin_action
from app.db import utcnow
from app.features.orders import service
from app.ids import next_public_id
from app.models.catalogue import Shop
from app.models.commerce import Dispute, Order
from app.models.identity import ADMIN_ROLES, User
from app.models.social import Conversation
from app.notify import notify
from app.settings_store import get_setting

DISPUTE_REASONS = ("not_received", "not_as_described", "damaged", "wrong_item", "no_show", "other")


def conversation_in_dispute(db: Session, convo: Conversation) -> bool:
    """Admins may open a chat when its order is in a dispute."""
    return (
        db.scalar(select(Dispute.id).join(Order, Order.id == Dispute.order_id).where(Order.conversation_id == convo.id).limit(1))
        is not None
    )


def open_dispute(db: Session, order: Order, buyer: User, reason: str, details: str) -> Dispute:
    if order.protected is False:
        raise HTTPException(409, "Cash and direct transfer deals are not protected, so they cannot be disputed here.")
    if order.buyer_id != buyer.id:
        raise HTTPException(404, "Order not found.")
    if db.scalar(select(Dispute.id).where(Dispute.order_id == order.id)):
        raise HTTPException(409, "This order already has a dispute.")
    service.transition(db, order, "disputed", buyer, reason)
    order.auto_confirm_at = None  # the payout is paused while the dispute is open
    dispute = Dispute(
        public_id=next_public_id(db, "D"),
        order_id=order.id,
        opened_by=buyer.id,
        reason=reason,
        details=details,
        response_due_at=utcnow() + timedelta(hours=get_setting(db, "dispute_response_hours")),
        evidence=[{"by": "buyer", "text": details, "image": None, "at": utcnow().isoformat()}] if details else [],
    )
    db.add(dispute)
    db.flush()
    shop = db.get(Shop, order.shop_id)
    if shop is not None:
        notify(
            db,
            shop.user_id,
            "dispute.opened",
            f"Problem reported on {order.public_id}",
            f"Respond within {get_setting(db, 'dispute_response_hours')} hours with your side and any evidence.",
            f"/seller/orders/{order.public_id}",
        )
    for admin in db.scalars(select(User).where(User.role.in_(ADMIN_ROLES), User.deleted_at.is_(None))):
        notify(
            db,
            admin.id,
            "dispute.opened",
            f"New dispute {dispute.public_id}",
            f"Order {order.public_id}: {reason.replace('_', ' ')}",
            "/admin/disputes",
        )
    return dispute


def add_evidence(dispute: Dispute, who: str, text: str, image: str | None = None) -> None:
    items: list[dict[str, Any]] = list(dispute.evidence or [])
    items.append({"by": who, "text": text, "image": image, "at": utcnow().isoformat()})
    dispute.evidence = items


def seller_respond(db: Session, dispute: Dispute, order: Order, seller: User, message: str) -> None:
    if dispute.status == "resolved":
        raise HTTPException(409, "This dispute is already resolved.")
    dispute.seller_response = message
    dispute.status = "under_review"
    add_evidence(dispute, "seller", message)
    notify(
        db,
        order.buyer_id,
        "dispute.update",
        f"The seller responded about {order.public_id}",
        "An Admin will review both sides.",
        f"/orders/{order.public_id}",
    )
    for admin in db.scalars(select(User).where(User.role.in_(ADMIN_ROLES), User.deleted_at.is_(None))):
        notify(db, admin.id, "dispute.update", f"Seller responded on {dispute.public_id}", "Ready for a decision.", "/admin/disputes")


def decide(db: Session, dispute: Dispute, order: Order, admin: User, decision: str, refund_item_kobo: int, note: str) -> None:
    """Admin ruling: full refund, partial refund or release to the seller. Both people are told the result."""
    if dispute.status == "resolved":
        raise HTTPException(409, "This dispute is already resolved.")
    if order.status != "disputed":
        raise HTTPException(409, "The order is not in dispute.")
    if decision == "partial_refund" and not 0 < refund_item_kobo < order.item_paid_kobo:
        raise HTTPException(422, "A partial refund must be more than zero and less than the item price.")
    log_admin_action(
        db,
        admin,
        f"dispute.{decision}",
        "dispute",
        dispute.public_id,
        reason=note,
        before={"status": dispute.status},
        after={"decision": decision, "refund_item_kobo": refund_item_kobo},
    )
    if decision == "full_refund":
        service.refund_item_amount(db, order, order.item_paid_kobo, f"Dispute {dispute.public_id}: full refund")
        service.transition(db, order, "refunded", admin, note)
        dispute.refund_item_kobo = order.item_paid_kobo
    elif decision == "partial_refund":
        service.refund_item_amount(db, order, refund_item_kobo, f"Dispute {dispute.public_id}: partial refund")
        service.confirm(db, order, admin, f"Dispute {dispute.public_id}: partial refund then release", count_deal=False)
        dispute.refund_item_kobo = refund_item_kobo
    else:
        service.confirm(db, order, admin, f"Dispute {dispute.public_id}: released to seller")
    dispute.resolution, dispute.decided_by, dispute.admin_note = decision, admin.id, note
    dispute.status, dispute.resolved_at = "resolved", utcnow()
    outcome = {
        "full_refund": "You were refunded in full.",
        "partial_refund": "You were partly refunded.",
        "release": "The payment was released to the seller.",
    }[decision]
    notify(
        db, order.buyer_id, "dispute.resolved", f"Dispute {dispute.public_id} resolved", f"{outcome} {note}", f"/orders/{order.public_id}"
    )
    shop = db.get(Shop, order.shop_id)
    if shop is not None:
        notify(
            db,
            shop.user_id,
            "dispute.resolved",
            f"Dispute {dispute.public_id} resolved",
            f"Decision: {decision.replace('_', ' ')}. {note}",
            f"/seller/orders/{order.public_id}",
        )
