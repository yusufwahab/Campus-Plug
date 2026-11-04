from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, case, func, or_, select

from app.db import utcnow
from app.deps import DB, CurrentUser, OptionalUser
from app.features.analytics.service import record
from app.features.catalogue.schemas import ListingCard, ListingDetail, ListingPage, SellerOut
from app.features.catalogue.service import cards, listing_detail, seller_out
from app.models.catalogue import Category, Listing, SavedItem, SearchLog, Shop
from app.models.growth import Boost
from app.models.identity import Campus

router = APIRouter(tags=["marketplace"])


def _sponsored(db: DB, rows: list[Listing]) -> set[int]:
    """Listings currently boosted. Shown with a Sponsored label."""
    ids = [r.id for r in rows]
    return set(db.scalars(select(Boost.listing_id).where(Boost.status == "active", Boost.listing_id.in_(ids)))) if ids else set()


Sort = Literal["relevance", "newest", "price_asc", "price_desc"]


def _live_query() -> Select[Any]:
    """Listings that may appear in discovery: active, not deleted, shop not on holiday or deleted."""
    return (
        select(Listing)
        .join(Shop, Shop.id == Listing.shop_id)
        .where(Listing.status == "active", Listing.deleted_at.is_(None), Shop.deleted_at.is_(None), Shop.holiday_mode.is_(False))
    )


def _filtered(
    q: str,
    *,
    type_: str | None,
    category: str | None,
    campus: str | None,
    location_id: int | None,
    min_price: int | None,
    max_price: int | None,
    condition: str | None,
    verified: bool,
    open_now: bool,
    sort: Sort,
) -> Select[Any]:
    query = _live_query()
    if q:
        like = f"%{q.lower().strip()}%"
        query = query.where(
            or_(
                func.lower(Listing.title).like(like),
                func.lower(Listing.description).like(like),
                func.lower(Shop.name).like(like),
                func.upper(Listing.public_id) == q.upper().strip(),
            )
        )
    if type_:
        query = query.where(Listing.type == type_)
    if category:
        query = query.join(Category, Category.id == Listing.category_id).where(Category.slug == category)
    if campus:
        query = query.join(Campus, Campus.id == Listing.campus_id).where(Campus.slug == campus)
    if location_id:
        query = query.where(Listing.location_id == location_id)
    if min_price is not None:
        query = query.where(Listing.price_kobo >= min_price)
    if max_price is not None:
        query = query.where(Listing.price_kobo <= max_price)
    if condition:
        query = query.where(Listing.condition == condition)
    if verified:
        query = query.where(Shop.verification_status == "verified")
    if open_now:
        query = query.where(Listing.open_now.is_(True))
    if sort == "newest":
        return query.order_by(Listing.created_at.desc())
    if sort == "price_asc":
        return query.order_by(Listing.price_kobo.asc())
    if sort == "price_desc":
        return query.order_by(Listing.price_kobo.desc())
    # Relevance: same hall first, then verified sellers, then well-rated sellers, then newest.
    rating = case((Shop.rating_count > 0, Shop.rating_sum * 100 / Shop.rating_count), else_=0)
    boosted = case((Listing.id.in_(select(Boost.listing_id).where(Boost.status == "active")), 1), else_=0)
    ordering = [boosted.desc(), case((Shop.verification_status == "verified", 1), else_=0).desc(), rating.desc(), Listing.created_at.desc()]
    if location_id:
        ordering.insert(0, case((Listing.location_id == location_id, 1), else_=0).desc())
    return query.order_by(*ordering)


@router.get("/listings", response_model=ListingPage)
def browse(
    db: DB,
    q: str = "",
    type: Literal["product", "service"] | None = None,
    category: str | None = None,
    campus: str | None = None,
    location_id: int | None = None,
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    condition: str | None = None,
    verified: bool = False,
    open_now: bool = False,
    sort: Sort = "relevance",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=60),
) -> ListingPage:
    query = _filtered(
        q, type_=type, category=category, campus=campus, location_id=location_id, min_price=min_price,
        max_price=max_price, condition=condition, verified=verified, open_now=open_now, sort=sort,
    )  # fmt: skip
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = list(db.scalars(query.offset((page - 1) * size).limit(size)))
    return ListingPage(items=cards(db, rows, _sponsored(db, rows)), total=total, page=page, size=size)


class SearchResult(BaseModel):
    listings: list[ListingCard]
    shops: list[SellerOut]
    total: int
    ask_campus: bool


@router.get("/search", response_model=SearchResult)
def search(
    db: DB,
    user: OptionalUser,
    q: str = Query("", max_length=200),
    type: Literal["product", "service"] | None = None,
    category: str | None = None,
    campus: str | None = None,
    location_id: int | None = None,
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    condition: str | None = None,
    verified: bool = False,
    open_now: bool = False,
    sort: Sort = "relevance",
) -> SearchResult:
    query = _filtered(
        q, type_=type, category=category, campus=campus, location_id=location_id, min_price=min_price,
        max_price=max_price, condition=condition, verified=verified, open_now=open_now, sort=sort,
    )  # fmt: skip
    rows = list(db.scalars(query.limit(40)))
    shops: list[Shop] = []
    if q.strip():
        like = f"%{q.lower().strip()}%"
        shops = list(
            db.scalars(
                select(Shop)
                .where(
                    Shop.deleted_at.is_(None),
                    Shop.holiday_mode.is_(False),
                    or_(func.lower(Shop.name).like(like), Shop.public_id == q.upper().strip()),
                )
                .limit(10)
            )
        )
        # Record every search, including ones with no results, so Admin can see unmet demand.
        db.add(SearchLog(user_id=user.id if user else None, query=q.strip()[:200], results=len(rows) + len(shops), created_at=utcnow()))
        db.commit()
    return SearchResult(
        listings=cards(db, rows, _sponsored(db, rows)),
        shops=[seller_out(db, s) for s in shops],
        total=len(rows),
        ask_campus=bool(q.strip()) and not rows and not shops,
    )


@router.get("/listings/{public_id}", response_model=ListingDetail)
def get_listing(public_id: str, db: DB) -> ListingDetail:
    listing = db.scalar(
        select(Listing).where(Listing.public_id == public_id.upper(), Listing.deleted_at.is_(None), Listing.status != "draft")
    )
    if listing is None or listing.status == "removed":
        raise HTTPException(404, "This listing is not available.")
    listing.views += 1
    record(db, "listing_view", campus_id=listing.campus_id, shop_id=listing.shop_id, listing_id=listing.id)
    db.commit()
    return listing_detail(db, listing)


class ShopPage(BaseModel):
    seller: SellerOut
    products: list[ListingCard]
    services: list[ListingCard]


@router.get("/shops/{slug}", response_model=ShopPage)
def get_shop(slug: str, db: DB) -> ShopPage:
    shop = db.scalar(select(Shop).where(Shop.slug == slug, Shop.deleted_at.is_(None)))
    if shop is None:
        raise HTTPException(404, "Shop not found.")
    live = list(
        db.scalars(
            select(Listing)
            .where(Listing.shop_id == shop.id, Listing.status == "active", Listing.deleted_at.is_(None))
            .order_by(Listing.id.desc())
        )
    )
    shown = [] if shop.holiday_mode else cards(db, live)
    return ShopPage(
        seller=seller_out(db, shop),
        products=[c for c in shown if c.type == "product"],
        services=[c for c in shown if c.type == "service"],
    )


class HomeFeed(BaseModel):
    open_now: list[ListingCard]
    new: list[ListingCard]
    popular: list[ListingCard]


@router.get("/home", response_model=HomeFeed)
def home_feed(db: DB, campus: str = "unilag") -> HomeFeed:
    base = _live_query().join(Campus, Campus.id == Listing.campus_id).where(Campus.slug == campus)
    open_now = list(db.scalars(base.where(Listing.open_now.is_(True), Listing.type == "service").order_by(Listing.id.desc()).limit(10)))
    new = list(db.scalars(base.order_by(Listing.created_at.desc(), Listing.id.desc()).limit(10)))
    popular = list(db.scalars(base.order_by(Listing.views.desc(), Listing.id.desc()).limit(10)))
    return HomeFeed(open_now=cards(db, open_now), new=cards(db, new), popular=cards(db, popular))


@router.get("/saved", response_model=list[ListingCard])
def saved(user: CurrentUser, db: DB) -> list[ListingCard]:
    rows = db.scalars(
        select(Listing)
        .join(SavedItem, SavedItem.listing_id == Listing.id)
        .where(SavedItem.user_id == user.id, Listing.deleted_at.is_(None))
        .order_by(SavedItem.id.desc())
    )
    return cards(db, list(rows))


@router.put("/saved/{public_id}", status_code=204)
def save(public_id: str, user: CurrentUser, db: DB) -> None:
    listing = db.scalar(select(Listing).where(Listing.public_id == public_id.upper(), Listing.deleted_at.is_(None)))
    if listing is None:
        raise HTTPException(404, "Listing not found.")
    if not db.scalar(select(SavedItem.id).where(SavedItem.user_id == user.id, SavedItem.listing_id == listing.id)):
        db.add(SavedItem(user_id=user.id, listing_id=listing.id))
        db.commit()


@router.delete("/saved/{public_id}", status_code=204)
def unsave(public_id: str, user: CurrentUser, db: DB) -> None:
    listing = db.scalar(select(Listing).where(Listing.public_id == public_id.upper()))
    if listing is not None:
        row = db.scalar(select(SavedItem).where(SavedItem.user_id == user.id, SavedItem.listing_id == listing.id))
        if row is not None:
            db.delete(row)
            db.commit()
