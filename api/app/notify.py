"""Event-driven notifications: in-app immediately, email / web push / SMS delivered by a background job."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.email import get_email
from app.adapters.push import get_push
from app.adapters.sms import get_sms
from app.jobs.core import enqueue, handler
from app.models.identity import User
from app.models.social import Notification, PushSubscription
from app.settings_store import get_setting

# Essential messages (orders, payments, payouts, disputes, security) cannot be turned off.
ESSENTIAL_KINDS = {
    "order.new", "order.accepted", "order.status", "order.cancelled", "order.refunded", "order.reminder",
    "payment.request", "payment.received", "payout.sent", "payout.held",
    "verification.decision", "dispute.opened", "dispute.update", "dispute.resolved", "account.warning", "security",
}  # fmt: skip


def notify(db: Session, user_id: int, kind: str, title: str, body: str = "", url: str = "/") -> Notification | None:
    """Creates the in-app notification and queues delivery. The caller commits.

    Optional kinds are skipped for users who turned them off; essential kinds always go through.
    """
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        return None
    essential = kind in ESSENTIAL_KINDS
    if not essential and not user.notify_optional:
        return None
    note = Notification(user_id=user_id, kind=kind, title=title, body=body, url=url, essential=essential)
    db.add(note)
    db.flush()
    enqueue(db, "deliver_notification", {"notification_id": note.id})
    return note


@handler("deliver_notification")
def deliver(db: Session, payload: dict) -> None:
    note = db.get(Notification, payload["notification_id"])
    if note is None:
        return
    user = db.get(User, note.user_id)
    if user is None or user.deleted_at is not None:
        return
    push = get_push()
    for sub in db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id)):
        if not push.send(sub.endpoint, sub.p256dh, sub.auth, note.title, note.body, note.url):
            db.delete(sub)
    if note.essential:
        get_email().send(user.email, note.title, f"{note.body}\n\nOpen: {note.url}")
        if user.phone and user.phone_verified and get_setting(db, "sms_enabled"):
            get_sms().send(user.phone, f"{note.title}. {note.body}"[:300])
