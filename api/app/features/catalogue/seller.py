from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.storage import MAX_BYTES, get_storage, public_url, sniff_image
from app.db import utcnow
from app.deps import DB, CurrentUser, SellerUser
from app.features.catalogue.schemas import (
    ImageOut,
    ListingCard,
    ListingDetail,
    ListingIn,
    ListingPatch,
    PayoutPreview,
    SellerOut,
    ShopSettingsIn,
    ShopStartIn,
    StatusIn,
)
from app.features.catalogue.service import assert_can_publish, cards, listing_detail, seller_out, set_expiry, unique_slug
from app.ids import next_public_id
from app.models.catalogue import Category, Listing, ListingImage, Shop
from app.models.identity import Campus, Location, User
from app.money import commission_for, resolve_commission_bps
from app.settings_store import get_setting

router = APIRouter(tags=["seller"])


def my_shop(db: Session, user: User) -> Shop:
    shop = db.scalar(select(Shop).where(Shop.user_id == user.id, Shop.deleted_at.is_(None)))
    if shop is None:
        raise HTTPException(404, "You have not created a shop yet.")
    return shop


def my_listing(db: Session, shop: Shop, public_id: str) -> Listing:
    listing = db.scalar(select(Listing).where(Listing.public_id == public_id, Listing.shop_id == shop.id, Listing.deleted_at.is_(None)))
    if listing is None:
        raise HTTPException(404, "Listing not found.")
    return listing


@router.post("/seller/start", response_model=SellerOut, status_code=201)
def start_shop(body: ShopStartIn, user: CurrentUser, db: DB) -> SellerOut:
    if not body.accept_rules:
        raise HTTPException(422, "You must accept the seller rules to open a shop.")
    if not user.email_verified:
        raise HTTPException(403, "Confirm your email address before opening a shop.")
    if db.scalar(select(Shop.id).where(Shop.user_id == user.id)):
        raise HTTPException(409, "You already have a shop.")
    if body.vendor_type == "vendor" and not get_setting(db, "allow_vendors"):
        raise HTTPException(403, "Only students can sell on Campus Plug right now.")
    campus_id = user.campus_id or db.scalar(select(Campus.id).where(Campus.enabled.is_(True)).order_by(Campus.id))
    if campus_id is None:
        raise HTTPException(409, "No campus is available yet.")
    if body.location_id is not None:
        loc = db.get(Location, body.location_id)
        if loc is None or loc.campus_id != campus_id:
            raise HTTPException(422, "That location does not belong to your campus.")
    shop = Shop(
        public_id=next_public_id(db, "SL"),
        user_id=user.id,
        slug=unique_slug(db, body.name),
        name=body.name,
        bio=body.bio,
        campus_id=campus_id,
        location_id=body.location_id or user.location_id,
        vendor_type=body.vendor_type,
        rules_accepted_at=utcnow(),
    )
    db.add(shop)
    if user.role == "buyer":
        user.role = "seller"
    db.commit()
    return seller_out(db, shop)


class ChecklistItem(BaseModel):
    key: str
    label: str
    done: bool
    href: str


class SellerOverview(BaseModel):
    shop: SellerOut
    rules_accepted: bool
    checklist: list[ChecklistItem]
    live_listings: int
    listing_limit: int | None
    payout_added: bool
    payout_review_required: bool


@router.get("/seller/overview", response_model=SellerOverview)
def overview(user: SellerUser, db: DB) -> SellerOverview:
    shop = my_shop(db, user)
    live = (
        db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.shop_id == shop.id, Listing.status == "active", Listing.deleted_at.is_(None))
        )
        or 0
    )
    payout = bool(shop.payout_account_number)
    checklist = [
        ChecklistItem(key="listing", label="Add your first listing", done=live > 0, href="/seller/listings/new"),
        ChecklistItem(key="verify", label="Verify your identity", done=shop.verification_status == "verified", href="/seller/verification"),
        ChecklistItem(key="payout", label="Add payout details", done=payout, href="/seller/settings"),
        ChecklistItem(key="share", label="Share your shop", done=shop.shared_at is not None, href=f"/shop/{shop.slug}"),
    ]
    verified = shop.verification_status == "verified"
    return SellerOverview(
        shop=seller_out(db, shop),
        rules_accepted=shop.rules_accepted_at is not None,
        checklist=checklist,
        live_listings=live,
        listing_limit=None if verified else get_setting(db, "unverified_listing_limit"),
        payout_added=payout,
        payout_review_required=shop.payout_review_required,
    )


@router.post("/seller/accept-rules", status_code=204)
def accept_rules(user: SellerUser, db: DB) -> None:
    """Shops opened for a seller by a Hall Rep stay unpublished until the seller accepts the rules themselves."""
    shop = my_shop(db, user)
    shop.rules_accepted_at = shop.rules_accepted_at or utcnow()
    db.commit()


@router.post("/seller/shared", status_code=204)
def mark_shared(user: SellerUser, db: DB) -> None:
    shop = my_shop(db, user)
    shop.shared_at = shop.shared_at or utcnow()
    db.commit()


class ShopSettingsOut(SellerOut):
    payout_bank: str | None
    payout_account_number_masked: str | None
    payout_account_name: str | None
    payout_review_required: bool


def _settings_out(db: Session, shop: Shop) -> ShopSettingsOut:
    number = shop.payout_account_number
    return ShopSettingsOut(
        **seller_out(db, shop).model_dump(),
        payout_bank=shop.payout_bank,
        payout_account_number_masked=f"******{number[-4:]}" if number else None,
        payout_account_name=shop.payout_account_name,
        payout_review_required=shop.payout_review_required,
    )


@router.get("/seller/settings", response_model=ShopSettingsOut)
def get_settings_(user: SellerUser, db: DB) -> ShopSettingsOut:
    return _settings_out(db, my_shop(db, user))


@router.patch("/seller/settings", response_model=ShopSettingsOut)
def update_settings(body: ShopSettingsIn, user: SellerUser, db: DB) -> ShopSettingsOut:
    shop = my_shop(db, user)
    data = body.model_dump(exclude_unset=True)
    payout_fields = {"payout_bank", "payout_account_number", "payout_account_name"}
    payout_changed = any(k in data and getattr(shop, k) != data[k] for k in payout_fields)
    if "location_id" in data and data["location_id"] is not None:
        loc = db.get(Location, data["location_id"])
        if loc is None or loc.campus_id != shop.campus_id:
            raise HTTPException(422, "That location does not belong to your campus.")
    for key, value in data.items():
        setattr(shop, key, value)
    # Changing payout details triggers another review before the next payout.
    if payout_changed and shop.verification_status == "verified":
        shop.payout_review_required = True
    # Holiday mode needs no extra work here: public discovery queries hide shops on holiday.
    db.commit()
    return _settings_out(db, shop)


@router.get("/listings/payout-preview", response_model=PayoutPreview)
def payout_preview(user: SellerUser, db: DB, price_kobo: int, category_id: int, seller_discount_kobo: int = 0) -> PayoutPreview:
    shop = my_shop(db, user)
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    bps = resolve_commission_bps(
        default_bps=get_setting(db, "commission_bps"),
        category_bps=category.commission_override_bps,
        seller_bps=shop.commission_override_bps,
    )
    price = max(price_kobo - seller_discount_kobo, 0)
    commission = commission_for(price, bps)
    return PayoutPreview(buyer_price_kobo=price, commission_bps=bps, commission_kobo=commission, seller_payout_kobo=price - commission)


def _validate_refs(db: Session, shop: Shop, category_id: int, location_id: int | None) -> Category:
    category = db.get(Category, category_id)
    if category is None or not category.enabled:
        raise HTTPException(422, "Choose a valid category.")
    if location_id is not None:
        loc = db.get(Location, location_id)
        if loc is None or loc.campus_id != shop.campus_id:
            raise HTTPException(422, "That location does not belong to your campus.")
    return category


@router.post("/listings", response_model=ListingDetail, status_code=201)
def create_listing(body: ListingIn, user: SellerUser, db: DB) -> ListingDetail:
    shop = my_shop(db, user)
    category = _validate_refs(db, shop, body.category_id, body.location_id)
    if body.publish:
        assert_can_publish(db, shop, category, body.price_kobo)
    listing = Listing(
        public_id=next_public_id(db, "P" if body.type == "product" else "S"),
        shop_id=shop.id,
        campus_id=shop.campus_id,
        status="active" if body.publish else "draft",
        **body.model_dump(exclude={"publish"}),
    )
    listing.location_id = body.location_id or shop.location_id
    db.add(listing)
    if body.publish:
        set_expiry(db, listing)
    db.commit()
    return listing_detail(db, listing)


@router.get("/seller/listings", response_model=list[ListingCard])
def my_listings(user: SellerUser, db: DB, status: str | None = None) -> list[ListingCard]:
    shop = my_shop(db, user)
    query = select(Listing).where(Listing.shop_id == shop.id, Listing.deleted_at.is_(None)).order_by(Listing.id.desc())
    if status:
        query = query.where(Listing.status == status)
    return cards(db, list(db.scalars(query)))


@router.get("/seller/listings/{public_id}", response_model=ListingDetail)
def my_listing_detail(public_id: str, user: SellerUser, db: DB) -> ListingDetail:
    return listing_detail(db, my_listing(db, my_shop(db, user), public_id))


@router.patch("/listings/{public_id}", response_model=ListingDetail)
def update_listing(public_id: str, body: ListingPatch, user: SellerUser, db: DB) -> ListingDetail:
    shop = my_shop(db, user)
    listing = my_listing(db, shop, public_id)
    data = body.model_dump(exclude_unset=True)
    category = _validate_refs(db, shop, data.get("category_id", listing.category_id), data.get("location_id"))
    new_price = data.get("price_kobo", listing.price_kobo)
    if listing.status == "active":
        assert_can_publish(db, shop, category, new_price, excluding_listing_id=listing.id)
    if "price_kobo" in data and data["price_kobo"] != listing.price_kobo:
        listing.previous_price_kobo, listing.price_changed_at = listing.price_kobo, utcnow()
    for key, value in data.items():
        setattr(listing, key, value)
    db.commit()
    return listing_detail(db, listing)


@router.post("/listings/{public_id}/status", response_model=ListingDetail)
def change_status(public_id: str, body: StatusIn, user: SellerUser, db: DB) -> ListingDetail:
    shop = my_shop(db, user)
    listing = my_listing(db, shop, public_id)
    if body.status == "active":
        assert_can_publish(db, shop, db.get(Category, listing.category_id), listing.price_kobo, excluding_listing_id=listing.id)  # type: ignore[arg-type]
        set_expiry(db, listing)
    listing.status = body.status
    if body.status == "removed":
        listing.deleted_at = utcnow()
    db.commit()
    return listing_detail(db, listing)


@router.post("/listings/{public_id}/still-available", response_model=ListingDetail)
def still_available(public_id: str, user: SellerUser, db: DB) -> ListingDetail:
    """One-tap renewal: extends the listing and brings it back if it had expired."""
    shop = my_shop(db, user)
    listing = my_listing(db, shop, public_id)
    if listing.status == "expired":
        assert_can_publish(db, shop, db.get(Category, listing.category_id), listing.price_kobo, excluding_listing_id=listing.id)  # type: ignore[arg-type]
        listing.status = "active"
    set_expiry(db, listing)
    db.commit()
    return listing_detail(db, listing)


@router.post("/listings/{public_id}/images", response_model=ImageOut, status_code=201)
async def upload_image(public_id: str, file: Annotated[UploadFile, File()], user: SellerUser, db: DB) -> ImageOut:
    shop = my_shop(db, user)
    listing = my_listing(db, shop, public_id)
    count = db.scalar(select(func.count()).select_from(ListingImage).where(ListingImage.listing_id == listing.id)) or 0
    limit = get_setting(db, "max_images_per_listing")
    if count >= limit:
        raise HTTPException(409, f"You can add up to {limit} images per listing.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "That image is too large (5 MB maximum).")
    ext, _mime = sniff_image(data)
    image = ListingImage(listing_id=listing.id, path=get_storage().save_public(data, ext), position=count)
    db.add(image)
    db.commit()
    return ImageOut(id=image.id, url=public_url(image.path))


@router.delete("/listings/{public_id}/images/{image_id}", status_code=204)
def delete_image(public_id: str, image_id: int, user: SellerUser, db: DB) -> None:
    listing = my_listing(db, my_shop(db, user), public_id)
    image = db.get(ListingImage, image_id)
    if image is None or image.listing_id != listing.id:
        raise HTTPException(404, "Image not found")
    path = image.path
    db.delete(image)
    db.commit()
    get_storage().delete_public(path)
