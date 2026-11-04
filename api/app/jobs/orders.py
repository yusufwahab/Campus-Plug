"""Scheduled order work: payouts, acceptance timeouts, automatic confirmation, reminders and dispute deadlines."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.features.orders import service
from app.jobs.core import handler
from app.models.catalogue import Shop
from app.models.commerce import Dispute, Order, Payout
from app.models.identity import ADMIN_ROLES, User
from app.models.social import Notification
from app.notify import notify
from app.settings_store import get_setting


@handler("process_payout")
def process_payout(db: Session, payload: dict) -> None:
    payout = db.get(Payout, payload["payout_id"])
    if payout is not None:
        service.process_payout(db, payout)  # raises on provider failure so the runner retries with backoff


@handler("retry_payouts", every=timedelta(minutes=15))
def retry_payouts(db: Session, payload: dict) -> None:
    """Picks up payouts that were held for missing details and are now ready, plus pending ones that lost their job."""
    for payout in db.scalars(select(Payout).where(Payout.status.in_(("pending", "held")))):
        shop = db.get(Shop, payout.shop_id)
        order = db.get(Order, payout.order_id)
        if payout.status == "held" and payout.hold_reason.startswith("Admin hold"):
            continue  # an Admin put this on hold on purpose: only an Admin releases it
        if payout.status == "held" and (
            shop is None or not shop.payout_account_number or shop.payout_review_required or (order and order.status == "disputed")
        ):
            continue
        payout.status, payout.hold_reason = "pending", ""
        service.process_payout(db, payout)


@handler("expire_unaccepted_orders", every=timedelta(minutes=10))
def expire_unaccepted(db: Session, payload: dict) -> None:
    """Sellers who do not accept in time lose the order: it is cancelled and the buyer is refunded in full."""
    for order in db.scalars(select(Order).where(Order.status == "paid", Order.accept_by.is_not(None), Order.accept_by <= utcnow())):
        service.cancel(db, order, None, "The seller did not accept in time")


@handler("expire_pending_payments", every=timedelta(minutes=30))
def expire_pending(db: Session, payload: dict) -> None:
    cutoff = utcnow() - timedelta(hours=get_setting(db, "pending_payment_hours"))
    for order in db.scalars(select(Order).where(Order.status == "pending_payment", Order.created_at <= cutoff)):
        service.cancel(db, order, None, "Payment was not completed in time")


@handler("auto_confirm_orders", every=timedelta(minutes=10))
def auto_confirm(db: Session, payload: dict) -> None:
    """Delivered orders confirm automatically after the confirmation window unless the buyer raised a dispute."""
    for order in db.scalars(
        select(Order).where(Order.status == "delivered", Order.auto_confirm_at.is_not(None), Order.auto_confirm_at <= utcnow())
    ):
        service.confirm(db, order, None, "Confirmed automatically after the confirmation window")
        notify(
            db,
            order.buyer_id,
            "order.status",
            f"{order.public_id} confirmed",
            "The confirmation window ended, so the seller has been paid.",
            f"/orders/{order.public_id}",
        )


@handler("dispute_deadlines", every=timedelta(minutes=30))
def dispute_deadlines(db: Session, payload: dict) -> None:
    """If the seller does not answer in time the dispute goes to an Admin for a decision anyway."""
    for dispute in db.scalars(
        select(Dispute).where(
            Dispute.status == "awaiting_seller", Dispute.response_due_at.is_not(None), Dispute.response_due_at <= utcnow()
        )
    ):
        dispute.status = "under_review"
        for admin in db.scalars(select(User).where(User.role.in_(ADMIN_ROLES), User.deleted_at.is_(None))):
            notify(
                db, admin.id, "dispute.update", f"Seller did not respond to {dispute.public_id}", "Ready for a decision.", "/admin/disputes"
            )


@handler("order_reminders", every=timedelta(minutes=15))
def reminders(db: Session, payload: dict) -> None:
    now = utcnow()
    for order in db.scalars(
        select(Order).where(
            Order.status == "paid", Order.accept_by.is_not(None), Order.accept_by <= now + timedelta(minutes=30), Order.accept_by > now
        )
    ):
        shop = db.get(Shop, order.shop_id)
        url = f"/seller/orders/{order.public_id}?reminder=accept"
        if shop and db.scalar(select(Notification.id).where(Notification.user_id == shop.user_id, Notification.url == url)) is None:
            notify(
                db,
                shop.user_id,
                "order.reminder",
                f"Accept {order.public_id} soon",
                "It is cancelled and refunded if you do not accept in time.",
                url,
            )
    for order in db.scalars(
        select(Order).where(
            Order.status == "delivered",
            Order.auto_confirm_at.is_not(None),
            Order.auto_confirm_at <= now + timedelta(hours=12),
            Order.auto_confirm_at > now,
        )
    ):
        url = f"/orders/{order.public_id}?reminder=confirm"
        if db.scalar(select(Notification.id).where(Notification.user_id == order.buyer_id, Notification.url == url)) is None:
            notify(
                db,
                order.buyer_id,
                "order.reminder",
                f"Did {order.public_id} arrive?",
                "Confirm delivery or report a problem. It confirms automatically soon.",
                url,
            )
