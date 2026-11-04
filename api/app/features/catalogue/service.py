import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.storage import public_url
from app.db import utcnow
from app.features.catalogue.schemas import ImageOut, ListingCard, ListingDetail, SellerOut
from app.models.catalogue import Category, Listing, ListingImage, Shop
from app.models.identity import Campus, Location
from app.models.trust import Vouch
from app.settings_store import get_setting

LIVE_STATUSES = ("active",)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "shop"


def unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    slug, n = base, 1
    while db.scalar(select(Shop.id).where(Shop.slug == slug)) is not None:
        n += 1
        slug = f"{base}-{n}"
    return slug


def rating_avg(shop: Shop) -> float | None:
    """Confirmed-deal reviews count double; reviews from deals outside the app count once."""
    weight = shop.rating_count * 2 + shop.unconfirmed_count
    return round((shop.rating_sum * 2 + shop.unconfirmed_sum) / weight, 1) if weight else None


def is_verified(shop: Shop) -> bool:
    return shop.verification_status == "verified"


def seller_out(db: Session, shop: Shop) -> SellerOut:
    location = db.get(Location, shop.location_id) if shop.location_id else None
    campus = db.get(Campus, shop.campus_id)
    return SellerOut(
        public_id=shop.public_id,
        slug=shop.slug,
        name=shop.name,
        bio=shop.bio,
        verification_status=shop.verification_status,
        trust_level=shop.trust_level,
        holiday_mode=shop.holiday_mode,
        confirmed_deals=shop.confirmed_deals,
        rating_count=shop.rating_count + shop.unconfirmed_count,
        rating_avg=rating_avg(shop),
        location_name=location.name if location else None,
        campus_name=campus.name if campus else None,
        vouched_by_rep=db.scalar(select(Vouch.id).where(Vouch.shop_id == shop.id).limit(1)) is not None,
    )


def first_images(db: Session, listing_ids: list[int]) -> dict[int, str]:
    if not listing_ids:
        return {}
    # The first photo of each listing. Selecting `path` next to MIN(position) in one GROUP BY works on SQLite only;
    # PostgreSQL rejects it, so find each listing's lowest position first and then read that row.
    first = (
        select(ListingImage.listing_id.label("listing_id"), func.min(ListingImage.position).label("position"))
        .where(ListingImage.listing_id.in_(listing_ids))
        .group_by(ListingImage.listing_id)
        .subquery()
    )
    rows = db.execute(
        select(ListingImage.listing_id, ListingImage.path).join(
            first, (ListingImage.listing_id == first.c.listing_id) & (ListingImage.position == first.c.position)
        )
    ).all()
    return {listing_id: public_url(path) for listing_id, path in rows}


def cards(db: Session, listings: list[Listing], sponsored_ids: set[int] | None = None) -> list[ListingCard]:
    if not listings:
        return []
    shops = {s.id: s for s in db.scalars(select(Shop).where(Shop.id.in_({lst.shop_id for lst in listings})))}
    cats = {c.id: c for c in db.scalars(select(Category).where(Category.id.in_({lst.category_id for lst in listings})))}
    loc_ids = {lst.location_id for lst in listings if lst.location_id}
    locs = {loc.id: loc for loc in db.scalars(select(Location).where(Location.id.in_(loc_ids)))} if loc_ids else {}
    images = first_images(db, [lst.id for lst in listings])
    out = []
    for lst in listings:
        shop, cat = shops[lst.shop_id], cats[lst.category_id]
        out.append(
            ListingCard(
                public_id=lst.public_id,
                title=lst.title,
                type=lst.type,
                price_kobo=lst.price_kobo,
                price_max_kobo=lst.price_max_kobo,
                category_slug=cat.slug,
                category_tint=cat.tint,
                location_name=locs[lst.location_id].name if lst.location_id in locs else None,
                image_url=images.get(lst.id),
                seller_name=shop.name,
                seller_slug=shop.slug,
                seller_verified=is_verified(shop),
                rating_avg=rating_avg(shop),
                sponsored=bool(sponsored_ids and lst.id in sponsored_ids),
                status=lst.status,
            )
        )
    return out


def listing_detail(db: Session, listing: Listing) -> ListingDetail:
    card = cards(db, [listing])[0]
    shop = db.get(Shop, listing.shop_id)
    campus = db.get(Campus, listing.campus_id)
    imgs = db.scalars(select(ListingImage).where(ListingImage.listing_id == listing.id).order_by(ListingImage.position, ListingImage.id))
    return ListingDetail(
        **card.model_dump(),
        description=listing.description,
        negotiable=listing.negotiable,
        condition=listing.condition,
        quantity=listing.quantity,
        variants=listing.variants or [],
        fulfilment=listing.fulfilment,
        delivery_fee_kobo=listing.delivery_fee_kobo,
        preorder=listing.preorder,
        availability=listing.availability,
        duration_min=listing.duration_min,
        deposit_kobo=listing.deposit_kobo,
        packages=listing.packages or [],
        images=[ImageOut(id=i.id, url=public_url(i.path)) for i in imgs],
        seller=seller_out(db, shop),  # type: ignore[arg-type]
        expires_at=listing.expires_at.isoformat() if listing.expires_at else None,
        created_at=listing.created_at.isoformat(),
        campus_name=campus.name if campus else None,
    )


def needs_verification(db: Session, category: Category, price_kobo: int) -> bool:
    """High-value items and Admin-selected categories require a verified seller before listing."""
    return (
        category.requires_verification
        or category.slug in get_setting(db, "verification_required_categories")
        or price_kobo >= get_setting(db, "high_value_threshold_kobo")
    )


def assert_can_publish(db: Session, shop: Shop, category: Category, price_kobo: int, *, excluding_listing_id: int | None = None) -> None:
    if shop.holiday_mode:
        raise HTTPException(409, "Turn off holiday mode to publish listings.")
    if shop.rules_accepted_at is None:
        raise HTTPException(403, "Accept the seller rules first.")
    if not is_verified(shop):
        if needs_verification(db, category, price_kobo):
            raise HTTPException(403, "This category or price needs a verified seller. Submit your verification first.")
        query = (
            select(func.count())
            .select_from(Listing)
            .where(Listing.shop_id == shop.id, Listing.status.in_(("active", "paused", "sold_out")), Listing.deleted_at.is_(None))
        )
        if excluding_listing_id:
            query = query.where(Listing.id != excluding_listing_id)
        limit = get_setting(db, "unverified_listing_limit")
        if (db.scalar(query) or 0) >= limit:
            raise HTTPException(403, f"Unverified sellers can have {limit} live listings. Verify your identity to list more.")


def set_expiry(db: Session, listing: Listing) -> None:
    listing.expires_at = utcnow() + timedelta(days=get_setting(db, "free_listing_days"))
