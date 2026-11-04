import csv
import io
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import distinct, func, select

from app.audit import log_admin_action
from app.db import utcnow
from app.deps import DB, AdminUser, SellerUser
from app.features.catalogue.seller import my_shop
from app.features.orders import ledger
from app.models.catalogue import Listing, SearchLog, Shop
from app.models.commerce import Dispute, Order
from app.models.growth import AnalyticsEvent, Review
from app.models.identity import Campus
from app.models.social import Conversation, PlugRequest, PlugResponse
from app.models.trust import Report

router = APIRouter(tags=["analytics"])

PAID = ("paid", "accepted", "preparing", "ready", "delivered", "confirmed", "paid_out", "disputed")


class AdminAnalytics(BaseModel):
    days: int
    campus: str | None
    searches: int
    empty_searches: int
    listing_views: int
    contacts: int
    chats: int
    requests: int
    request_responses: int
    orders: int
    confirmed_deals: int
    reviews: int
    repeat_buyers: int
    active_sellers: int
    reports: int
    disputes: int
    revenue_kobo: int
    commission_kobo: int
    top_empty_searches: list[dict[str, Any]]


def compute(db: DB, days: int, campus: str | None) -> AdminAnalytics:
    since = utcnow() - timedelta(days=days)
    campus_id = db.scalar(select(Campus.id).where(Campus.slug == campus)) if campus else None

    def events(kind: str) -> int:
        query = select(func.count()).select_from(AnalyticsEvent).where(AnalyticsEvent.kind == kind, AnalyticsEvent.created_at >= since)
        if campus_id:
            query = query.where(AnalyticsEvent.campus_id == campus_id)
        return db.scalar(query) or 0

    def count(model: Any, *where: Any) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    shop_in_campus = [Shop.campus_id == campus_id] if campus_id else []
    order_q = [Order.created_at >= since, *([Order.shop_id.in_(select(Shop.id).where(*shop_in_campus))] if campus_id else [])]
    buyer_orders = db.execute(
        select(Order.buyer_id, func.count()).where(Order.status.in_(("confirmed", "paid_out")), *order_q).group_by(Order.buyer_id)
    ).all()
    empty = db.execute(
        select(SearchLog.query, func.count())
        .where(SearchLog.results == 0, SearchLog.created_at >= since)
        .group_by(SearchLog.query)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    revenue = (
        db.scalar(
            select(func.coalesce(func.sum(Order.buyer_total_kobo), 0)).where(Order.status.in_(PAID), Order.protected.is_(True), *order_q)
        )
        or 0
    )
    return AdminAnalytics(
        days=days,
        campus=campus,
        searches=count(SearchLog, SearchLog.created_at >= since),
        empty_searches=count(SearchLog, SearchLog.results == 0, SearchLog.created_at >= since),
        listing_views=events("listing_view"),
        contacts=events("contact"),
        chats=count(Conversation, Conversation.created_at >= since),
        requests=count(PlugRequest, PlugRequest.created_at >= since, *([PlugRequest.campus_id == campus_id] if campus_id else [])),
        request_responses=count(PlugResponse, PlugResponse.created_at >= since),
        orders=count(Order, *order_q),
        confirmed_deals=count(Order, Order.status.in_(("confirmed", "paid_out")), *order_q),
        reviews=count(Review, Review.created_at >= since),
        repeat_buyers=sum(1 for _, n in buyer_orders if n > 1),
        active_sellers=db.scalar(select(func.count(distinct(Order.shop_id))).where(Order.status.in_(PAID), *order_q)) or 0,
        reports=count(Report, Report.created_at >= since),
        disputes=count(Dispute, Dispute.created_at >= since),
        revenue_kobo=int(revenue),
        commission_kobo=-ledger.balance(db, ledger.PLATFORM_REVENUE),
        top_empty_searches=[{"query": q, "count": n} for q, n in empty],
    )


@router.get("/admin/analytics", response_model=AdminAnalytics)
def admin_analytics(admin: AdminUser, db: DB, days: int = Query(30, ge=1, le=365), campus: str | None = None) -> AdminAnalytics:
    return compute(db, days, campus)


@router.get("/admin/analytics.csv")
def admin_analytics_csv(admin: AdminUser, db: DB, days: int = Query(30, ge=1, le=365), campus: str | None = None) -> Response:
    data = compute(db, days, campus).model_dump(exclude={"top_empty_searches"})
    log_admin_action(db, admin, "export.csv", "export", "analytics", reason=f"Exported analytics for {days} days")
    db.commit()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["metric", "value"])
    writer.writerows(data.items())
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="analytics.csv"'})


class SellerAnalytics(BaseModel):
    days: int
    listing_views: int
    contacts: int
    orders: int
    confirmed_deals: int
    conversion_pct: float
    rating_avg: float | None
    reviews: int
    top_listings: list[dict[str, Any]]


@router.get("/seller/analytics", response_model=SellerAnalytics)
def seller_analytics(user: SellerUser, db: DB, days: int = Query(30, ge=1, le=365)) -> SellerAnalytics:
    from app.features.catalogue.service import rating_avg

    shop = my_shop(db, user)
    since: datetime = utcnow() - timedelta(days=days)

    def events(kind: str) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(AnalyticsEvent.shop_id == shop.id, AnalyticsEvent.kind == kind, AnalyticsEvent.created_at >= since)
            )
            or 0
        )

    views, contacts = events("listing_view"), events("contact")
    orders = (
        db.scalar(
            select(func.count()).select_from(Order).where(Order.shop_id == shop.id, Order.status.in_(PAID), Order.created_at >= since)
        )
        or 0
    )
    deals = (
        db.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.shop_id == shop.id, Order.status.in_(("confirmed", "paid_out")), Order.created_at >= since)
        )
        or 0
    )
    top = db.scalars(
        select(Listing).where(Listing.shop_id == shop.id, Listing.deleted_at.is_(None)).order_by(Listing.views.desc()).limit(5)
    )
    return SellerAnalytics(
        days=days,
        listing_views=views,
        contacts=contacts,
        orders=orders,
        confirmed_deals=deals,
        conversion_pct=round(orders * 100 / views, 1) if views else 0.0,
        rating_avg=rating_avg(shop),
        reviews=shop.rating_count + shop.unconfirmed_count,
        top_listings=[{"public_id": lst.public_id, "title": lst.title, "views": lst.views} for lst in top],
    )
