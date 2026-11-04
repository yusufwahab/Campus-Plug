from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.audit import log_admin_action
from app.deps import DB, AdminUser
from app.features.orders import disputes, ledger
from app.features.orders.router import order_out
from app.features.orders.schemas import OrderOut
from app.jobs.core import enqueue
from app.models.catalogue import Category, Shop
from app.models.commerce import Dispute, LedgerEntry, Order, Payment, Payout, Refund
from app.models.identity import User
from app.settings_store import get_setting

router = APIRouter(prefix="/admin", tags=["admin"])


class OrderRow(BaseModel):
    public_id: str
    status: str
    listing_title: str
    buyer_total_kobo: int
    commission_kobo: int
    protected: bool
    created_at: str
    shop_name: str


@router.get("/orders", response_model=list[OrderRow])
def orders(
    admin: AdminUser, db: DB, q: str = "", status: str = "", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)
) -> list[OrderRow]:
    query = select(Order, Shop).join(Shop, Shop.id == Order.shop_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(Order.public_id == q.upper(), func.lower(Order.listing_title).like(like), func.lower(Shop.name).like(like)))
    if status:
        query = query.where(Order.status == status)
    rows = db.execute(query.order_by(Order.id.desc()).offset((page - 1) * size).limit(size)).all()
    return [
        OrderRow(
            public_id=o.public_id,
            status=o.status,
            listing_title=o.listing_title,
            buyer_total_kobo=o.buyer_total_kobo,
            commission_kobo=o.commission_kobo - o.commission_returned_kobo,
            protected=o.protected,
            created_at=o.created_at.isoformat(),
            shop_name=s.name,
        )
        for o, s in rows
    ]


@router.get("/orders/{public_id}", response_model=OrderOut)
def order_detail(public_id: str, admin: AdminUser, db: DB) -> OrderOut:
    order = db.scalar(select(Order).where(Order.public_id == public_id.upper()))
    if order is None:
        raise HTTPException(404, "Order not found")
    return order_out(db, order, admin, "admin")


class PaymentRow(BaseModel):
    reference: str
    order_id: str
    provider: str
    status: str
    amount_kobo: int
    fee_kobo: int
    created_at: str


@router.get("/payments", response_model=list[PaymentRow])
def payments(
    admin: AdminUser, db: DB, status: str = "", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)
) -> list[PaymentRow]:
    query = select(Payment, Order).join(Order, Order.id == Payment.order_id)
    if status:
        query = query.where(Payment.status == status)
    rows = db.execute(query.order_by(Payment.id.desc()).offset((page - 1) * size).limit(size)).all()
    return [
        PaymentRow(
            reference=p.reference,
            order_id=o.public_id,
            provider=p.provider,
            status=p.status,
            amount_kobo=p.amount_kobo,
            fee_kobo=p.fee_kobo,
            created_at=p.created_at.isoformat(),
        )
        for p, o in rows
    ]


class PayoutRow(BaseModel):
    id: int
    order_id: str
    shop_name: str
    amount_kobo: int
    status: str
    hold_reason: str
    created_at: str


@router.get("/payouts", response_model=list[PayoutRow])
def payouts(admin: AdminUser, db: DB, status: str = "", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)) -> list[PayoutRow]:
    query = select(Payout, Order, Shop).join(Order, Order.id == Payout.order_id).join(Shop, Shop.id == Payout.shop_id)
    if status:
        query = query.where(Payout.status == status)
    rows = db.execute(query.order_by(Payout.id.desc()).offset((page - 1) * size).limit(size)).all()
    return [
        PayoutRow(
            id=p.id,
            order_id=o.public_id,
            shop_name=s.name,
            amount_kobo=p.amount_kobo,
            status=p.status,
            hold_reason=p.hold_reason,
            created_at=p.created_at.isoformat(),
        )
        for p, o, s in rows
    ]


class PayoutAction(BaseModel):
    action: Literal["release", "hold"]
    reason: str = Field(min_length=3)


@router.post("/payouts/{payout_id}/action", response_model=PayoutRow)
def payout_action(payout_id: int, body: PayoutAction, admin: AdminUser, db: DB) -> PayoutRow:
    """Releases a held payout (queues it for sending) or holds a pending one."""
    payout = db.get(Payout, payout_id)
    order = db.get(Order, payout.order_id) if payout else None
    shop = db.get(Shop, payout.shop_id) if payout else None
    if payout is None or order is None or shop is None:
        raise HTTPException(404, "Payout not found")
    if body.action == "release":
        if payout.status != "held":
            raise HTTPException(409, "Only held payouts can be released.")
        if order.status == "disputed":
            raise HTTPException(409, "The order is in a dispute: decide the dispute first.")
        if not shop.payout_account_number:
            raise HTTPException(409, "The seller has not added payout details.")
        log_admin_action(
            db,
            admin,
            "payout.released",
            "payout",
            payout.id,
            reason=body.reason,
            before={"status": payout.status},
            after={"status": "pending"},
        )
        payout.status, payout.hold_reason = "pending", ""
        shop.payout_review_required = False
        enqueue(db, "process_payout", {"payout_id": payout.id})
    else:
        if payout.status != "pending":
            raise HTTPException(409, "Only pending payouts can be held.")
        log_admin_action(
            db, admin, "payout.held", "payout", payout.id, reason=body.reason, before={"status": payout.status}, after={"status": "held"}
        )
        payout.status, payout.hold_reason = "held", f"Admin hold: {body.reason}"[:200]
    db.commit()
    return PayoutRow(
        id=payout.id,
        order_id=order.public_id,
        shop_name=shop.name,
        amount_kobo=payout.amount_kobo,
        status=payout.status,
        hold_reason=payout.hold_reason,
        created_at=payout.created_at.isoformat(),
    )


class CommissionOut(BaseModel):
    default_bps: int
    provider_fee_absorbed: bool
    instant_split: bool
    categories: list[dict[str, Any]]
    sellers: list[dict[str, Any]]
    commission_earned_kobo: int
    provider_fees_kobo: int
    promo_cost_kobo: int


@router.get("/commission", response_model=CommissionOut)
def commission(admin: AdminUser, db: DB) -> CommissionOut:
    cats = [
        {"name": c.name, "bps": c.commission_override_bps}
        for c in db.scalars(select(Category).where(Category.commission_override_bps.is_not(None)))
    ]
    sellers = [
        {"name": s.name, "public_id": s.public_id, "bps": s.commission_override_bps}
        for s in db.scalars(select(Shop).where(Shop.commission_override_bps.is_not(None)))
    ]
    return CommissionOut(
        default_bps=get_setting(db, "commission_bps"),
        provider_fee_absorbed=bool(get_setting(db, "provider_fee_absorbed")),
        instant_split=bool(get_setting(db, "instant_split")),
        categories=cats,
        sellers=sellers,
        commission_earned_kobo=-ledger.balance(db, ledger.PLATFORM_REVENUE),
        provider_fees_kobo=ledger.balance(db, ledger.PROVIDER_FEES),
        promo_cost_kobo=ledger.balance(db, ledger.PROMO_COST),
    )


class RevenueOut(BaseModel):
    gmv_kobo: int
    commission_kobo: int
    orders_paid: int
    orders_confirmed: int
    refunded_kobo: int
    held_in_escrow_kobo: int
    owed_to_sellers_kobo: int


@router.get("/revenue", response_model=RevenueOut)
def revenue(admin: AdminUser, db: DB) -> RevenueOut:
    paid_statuses = ("paid", "accepted", "preparing", "ready", "delivered", "confirmed", "paid_out", "disputed")
    gmv = (
        db.scalar(
            select(func.coalesce(func.sum(Order.buyer_total_kobo), 0)).where(Order.status.in_(paid_statuses), Order.protected.is_(True))
        )
        or 0
    )
    refunded = db.scalar(select(func.coalesce(func.sum(Refund.amount_kobo), 0))) or 0
    return RevenueOut(
        gmv_kobo=int(gmv),
        commission_kobo=-ledger.balance(db, ledger.PLATFORM_REVENUE),
        orders_paid=db.scalar(select(func.count()).select_from(Order).where(Order.status.in_(paid_statuses), Order.protected.is_(True)))
        or 0,
        orders_confirmed=db.scalar(select(func.count()).select_from(Order).where(Order.status.in_(("confirmed", "paid_out")))) or 0,
        refunded_kobo=int(refunded),
        held_in_escrow_kobo=-ledger.balance(db, ledger.ESCROW),
        owed_to_sellers_kobo=-ledger.balance(db, ledger.SELLER_PAYABLE),
    )


class LedgerRow(BaseModel):
    group_id: str
    kind: str
    account: str
    amount_kobo: int
    order_id: int | None
    created_at: str


@router.get("/ledger", response_model=list[LedgerRow])
def ledger_entries(admin: AdminUser, db: DB, page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)) -> list[LedgerRow]:
    rows = db.scalars(select(LedgerEntry).order_by(LedgerEntry.id.desc()).offset((page - 1) * size).limit(size))
    return [
        LedgerRow(
            group_id=r.group_id,
            kind=r.kind,
            account=r.account,
            amount_kobo=r.amount_kobo,
            order_id=r.order_id,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


# ---- disputes ---------------------------------------------------------------------------------------------------------


class DisputeRow(BaseModel):
    public_id: str
    order_id: str
    status: str
    reason: str
    resolution: str
    created_at: str


@router.get("/disputes", response_model=list[DisputeRow])
def disputes_list(admin: AdminUser, db: DB, status: str = "") -> list[DisputeRow]:
    query = select(Dispute, Order).join(Order, Order.id == Dispute.order_id)
    if status:
        query = query.where(Dispute.status == status)
    rows = db.execute(query.order_by(Dispute.id.desc()).limit(100)).all()
    return [
        DisputeRow(
            public_id=d.public_id,
            order_id=o.public_id,
            status=d.status,
            reason=d.reason,
            resolution=d.resolution,
            created_at=d.created_at.isoformat(),
        )
        for d, o in rows
    ]


class DisputeDetail(BaseModel):
    order: OrderOut
    conversation_id: int | None


@router.get("/disputes/{public_id}", response_model=DisputeDetail)
def dispute_detail(public_id: str, admin: AdminUser, db: DB) -> DisputeDetail:
    dispute = db.scalar(select(Dispute).where(Dispute.public_id == public_id.upper()))
    order = db.get(Order, dispute.order_id) if dispute else None
    if dispute is None or order is None:
        raise HTTPException(404, "Dispute not found")
    return DisputeDetail(order=order_out(db, order, admin, "admin"), conversation_id=order.conversation_id)


class DecisionIn(BaseModel):
    decision: Literal["full_refund", "partial_refund", "release"]
    refund_item_kobo: int = Field(default=0, ge=0)
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/disputes/{public_id}/decide", response_model=DisputeDetail)
def decide(public_id: str, body: DecisionIn, admin: AdminUser, db: DB) -> DisputeDetail:
    dispute = db.scalar(select(Dispute).where(Dispute.public_id == public_id.upper()))
    order = db.get(Order, dispute.order_id) if dispute else None
    if dispute is None or order is None:
        raise HTTPException(404, "Dispute not found")
    buyer = db.get(User, order.buyer_id)
    shop = db.get(Shop, order.shop_id)
    if admin.id in (buyer.id if buyer else 0, shop.user_id if shop else 0):
        raise HTTPException(403, "You cannot decide a dispute you are part of.")
    disputes.decide(db, dispute, order, admin, body.decision, body.refund_item_kobo, body.reason)
    db.commit()
    return DisputeDetail(order=order_out(db, order, admin, "admin"), conversation_id=order.conversation_id)
