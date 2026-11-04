"""Scheduled work that is not tied to a single event. Order handlers live in app/features/orders."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.jobs.core import handler
from app.models.catalogue import Listing, Shop
from app.models.growth import Boost
from app.models.social import Notification, PlugRequest
from app.notify import notify


@handler("expire_listings", every=timedelta(minutes=30))
def expire_listings(db: Session, payload: dict) -> None:
    """Expires listings past their date and reminds sellers three days before (once per listing)."""
    now = utcnow()
    for listing in db.scalars(
        select(Listing).where(
            Listing.status == "active", Listing.deleted_at.is_(None), Listing.expires_at.is_not(None), Listing.expires_at <= now
        )
    ):
        listing.status = "expired"
        shop = db.get(Shop, listing.shop_id)
        if shop:
            notify(db, shop.user_id, "listing.expired", f"{listing.title} expired", "Tap Still available to renew it.", "/seller/listings")
    soon = now + timedelta(days=3)
    for listing in db.scalars(
        select(Listing).where(
            Listing.status == "active", Listing.deleted_at.is_(None), Listing.expires_at.is_not(None), Listing.expires_at <= soon
        )
    ):
        shop = db.get(Shop, listing.shop_id)
        if shop is None:
            continue
        url = f"/seller/listings?expiring={listing.public_id}"
        if db.scalar(select(Notification.id).where(Notification.user_id == shop.user_id, Notification.url == url)) is None:
            notify(db, shop.user_id, "listing.expiring", f"{listing.title} expires soon", "Is it still available? Tap to renew.", url)


@handler("expire_requests", every=timedelta(minutes=30))
def expire_requests(db: Session, payload: dict) -> None:
    now = utcnow()
    for req in db.scalars(
        select(PlugRequest).where(PlugRequest.status == "open", PlugRequest.deadline.is_not(None), PlugRequest.deadline <= now)
    ):
        req.status = "expired"
        notify(
            db,
            req.buyer_id,
            "request.expired",
            f'Your request "{req.title}" expired',
            "Post it again if you still need it.",
            f"/requests/{req.id}",
        )


@handler("end_boosts", every=timedelta(hours=1))
def end_boosts(db: Session, payload: dict) -> None:
    for boost in db.scalars(select(Boost).where(Boost.status == "active", Boost.ends_at.is_not(None), Boost.ends_at <= utcnow())):
        boost.status = "ended"
