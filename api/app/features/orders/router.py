from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.payments import LocalProvider, get_provider
from app.adapters.storage import MAX_BYTES, get_storage, sniff_image
from app.banks import BANKS
from app.config import get_settings
from app.db import utcnow
from app.deps import DB, CurrentUser, SellerUser
from app.features.orders import disputes, service
from app.features.orders.schemas import (
    CancelIn,
    DisputeOut,
    EarningsOut,
    EventOut,
    OfflineDealIn,
    OrderCreate,
    OrderOut,
    PayOut,
    ProblemIn,
    RespondIn,
    StageIn,
)
from app.features.promotions import purchases
from app.models.catalogue import Listing, Shop
from app.models.commerce import Dispute, Order, OrderEvent, Payment, Payout, WebhookEvent
from app.models.growth import Purchase
from app.models.identity import ADMIN_ROLES, User
from app.models.social import Conversation, Message
from app.notify import notify
from app.ratelimit import rate_limit
from app.security import create_token, decode_local_token
from app.settings_store import get_setting

router = APIRouter(tags=["orders"])


# ---- helpers --------------------------------------------------------------------------------------------------------


def role_in(db: Session, user: User, order: Order) -> str | None:
    if order.buyer_id == user.id:
        return "buyer"
    shop = db.get(Shop, order.shop_id)
    if shop is not None and shop.user_id == user.id:
        return "seller"
    if user.role in ADMIN_ROLES and getattr(user, "token_aal", 1) >= 2:
        return "admin"
    return None


def load(db: Session, user: User, public_id: str) -> tuple[Order, str]:
    order = db.scalar(select(Order).where(Order.public_id == public_id.upper()))
    role = role_in(db, user, order) if order else None
    if order is None or role is None:
        raise HTTPException(404, "Order not found.")
    return order, role


def _actions(db: Session, order: Order, role: str) -> list[str]:
    s, out = order.status, []
    is_app = order.payment_method == "app"
    if role == "buyer":
        if s == "pending_payment":
            out += ["pay", "cancel"]
        if s == "paid":
            out.append("cancel")
        service_cancel_window = timedelta(hours=get_setting(db, "service_cancel_hours"))
        if (
            s in ("accepted", "preparing", "ready")
            and order.listing_type == "service"
            and order.booking_at is not None
            and order.booking_at - utcnow() >= service_cancel_window
        ):
            out.append("cancel")
        if s == "delivered":
            out.append("confirm")
        if s in ("accepted", "preparing", "ready", "delivered") and order.protected and is_app:
            out.append("problem")
        if s == "accepted" and not is_app:
            out.append("confirm_offline")
    if role == "seller":
        if s == "paid":
            out += ["accept", "decline"]
        if s == "accepted":
            out += ["preparing", "ready"] if is_app else []
        if s == "preparing":
            out.append("ready")
        if s == "ready":
            out.append("delivered")
        if s in ("accepted", "preparing", "ready") and is_app:
            out.append("cancel")
        if (
            order.listing_type == "service"
            and s in ("accepted", "preparing", "ready")
            and order.booking_at
            and order.booking_at < utcnow()
            and is_app
        ):
            out.append("buyer_no_show")
        if s == "accepted" and not is_app:
            out.append("confirm_offline")
    return out


def order_out(db: Session, order: Order, viewer: User, role: str) -> OrderOut:
    shop = db.get(Shop, order.shop_id)
    buyer = db.get(User, order.buyer_id)
    listing = db.get(Listing, order.listing_id)
    convo = db.get(Conversation, order.conversation_id) if order.conversation_id else None
    other_phone = None
    if convo is not None and convo.phone_unlocked_by_payment:
        other = db.get(User, shop.user_id) if (role == "buyer" and shop) else buyer
        other_phone = other.phone if other else None
    dispute = db.scalar(select(Dispute).where(Dispute.order_id == order.id))
    events = db.scalars(select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id))
    payout = db.scalar(select(Payout).where(Payout.order_id == order.id)) if role != "buyer" else None
    from app.features.promotions.reviews import review_exists

    out = OrderOut(
        public_id=order.public_id,
        status=order.status,
        role=role,  # type: ignore[arg-type]
        listing_id=listing.public_id if listing else "",
        listing_title=order.listing_title,
        listing_type=order.listing_type,
        quantity=order.quantity,
        unit_price_kobo=order.unit_price_kobo,
        seller_discount_kobo=order.seller_discount_kobo,
        platform_discount_kobo=order.platform_discount_kobo,
        item_paid_kobo=order.item_paid_kobo,
        delivery_fee_kobo=order.delivery_fee_kobo,
        buyer_total_kobo=order.buyer_total_kobo,
        fulfilment=order.fulfilment,
        booking_at=order.booking_at.isoformat() if order.booking_at else None,
        deposit_only=order.deposit_only,
        protected=order.protected,
        payment_method=order.payment_method,
        note=order.note,
        conversation_id=order.conversation_id,
        other_party=(shop.name if shop else "Seller") if role == "buyer" else (buyer.full_name.split(" ")[0] if buyer else "Buyer"),
        other_phone=other_phone,
        created_at=order.created_at.isoformat(),
        paid_at=order.paid_at.isoformat() if order.paid_at else None,
        accept_by=order.accept_by.isoformat() if order.accept_by else None,
        auto_confirm_at=order.auto_confirm_at.isoformat() if order.auto_confirm_at else None,
        cancel_reason=order.cancel_reason,
        refunded_item_kobo=order.refunded_item_kobo,
        actions=_actions(db, order, role),
        timeline=[EventOut(status=e.to_status, note=e.note, at=e.created_at.isoformat()) for e in events],
        dispute=_dispute_out(dispute, viewer) if dispute else None,
        can_review=role == "buyer" and order.status in ("confirmed", "paid_out") and not review_exists(db, order),
    )
    if role in ("seller", "admin"):
        out.commission_bps, out.commission_kobo = order.commission_bps, order.commission_kobo - order.commission_returned_kobo
        out.seller_amount_kobo, out.provider_fee_kobo = service.payable_to_seller(order), order.provider_fee_kobo
        out.payout_status = payout.status if payout else None
    return out


def _dispute_out(d: Dispute, viewer: User) -> DisputeOut:
    evidence = [
        {
            **e,
            "image": f"/api/v1/files/evidence/{create_token(str(viewer.id), purpose='file', minutes=10, extra={'path': e['image'], 'dispute': d.id})}"
            if e.get("image")
            else None,
        }
        for e in (d.evidence or [])
    ]
    return DisputeOut(
        public_id=d.public_id,
        status=d.status,
        reason=d.reason,
        details=d.details,
        seller_response=d.seller_response,
        resolution=d.resolution,
        refund_item_kobo=d.refund_item_kobo,
        admin_note=d.admin_note,
        response_due_at=d.response_due_at.isoformat() if d.response_due_at else None,
        evidence=evidence,
        opened_by_me=d.opened_by == viewer.id,
    )


# ---- creating orders and paying ---------------------------------------------------------------------------------------


@router.post("/orders", response_model=OrderOut, status_code=201, dependencies=[Depends(rate_limit("order-create", 30, 3600))])
def create(body: OrderCreate, user: CurrentUser, db: DB) -> OrderOut:
    return _create(body, user, db)


def _create(body: OrderCreate, user: User, db: Session) -> OrderOut:
    convo_id = request_message_id = None
    agreed_unit = agreed_delivery = None
    quantity, fulfilment = body.quantity, body.fulfilment
    if body.message_id is not None:
        msg = db.get(Message, body.message_id)
        convo = db.get(Conversation, msg.conversation_id) if msg else None
        if msg is None or msg.kind != "payment_request" or convo is None or convo.buyer_id != user.id:
            raise HTTPException(404, "That payment request does not exist.")
        existing = db.scalar(select(Order).where(Order.request_message_id == msg.id, Order.status == "pending_payment"))
        if existing is not None:
            return order_out(db, existing, user, "buyer")
        if (msg.payload or {}).get("status") != "pending":
            raise HTTPException(409, "This payment request has already been used.")
        listing = db.scalar(select(Listing).where(Listing.public_id == msg.payload["listing_id"]))
        agreed_unit, quantity = int(msg.payload["agreed_price_kobo"]), int(msg.payload["quantity"])
        agreed_delivery = int(msg.payload.get("delivery_fee_kobo", 0))
        fulfilment = "delivery" if agreed_delivery else body.fulfilment
        convo_id, request_message_id = convo.id, msg.id
    elif body.listing_id:
        listing = db.scalar(select(Listing).where(Listing.public_id == body.listing_id.upper(), Listing.deleted_at.is_(None)))
    else:
        raise HTTPException(422, "Choose a listing or a payment request.")
    if listing is None:
        raise HTTPException(404, "That listing is not available.")
    extra: dict[str, Any] = {}
    if body.promo_code:
        from app.features.promotions.promos import price_with_promo

        extra = price_with_promo(
            db, user, listing, body.promo_code, agreed_unit if agreed_unit is not None else listing.price_kobo, quantity
        )
    order = service.create_order(
        db, buyer=user, listing=listing, quantity=quantity, fulfilment=fulfilment, booking_at=body.booking_at, agreed_unit_price_kobo=agreed_unit,
        agreed_delivery_fee_kobo=agreed_delivery, conversation_id=convo_id, request_message_id=request_message_id, note=body.note, **extra,
    )  # fmt: skip
    if order.promo_code_id is not None:
        from app.features.promotions.promos import redeem

        redeem(db, order, user)
    if request_message_id is not None:
        msg = db.get(Message, request_message_id)
        if msg is not None:
            msg.payload = {**(msg.payload or {}), "status": "ordered", "order_id": order.public_id}
    db.commit()
    return order_out(db, order, user, "buyer")


@router.get("/orders", response_model=list[OrderOut])
def my_orders(user: CurrentUser, db: DB, status: str | None = None) -> list[OrderOut]:
    query = select(Order).where(Order.buyer_id == user.id).order_by(Order.id.desc()).limit(100)
    if status:
        query = query.where(Order.status == status)
    return [order_out(db, o, user, "buyer") for o in db.scalars(query)]


@router.get("/seller/orders", response_model=list[OrderOut])
def seller_orders(user: SellerUser, db: DB, status: str | None = None) -> list[OrderOut]:
    shop = db.scalar(select(Shop).where(Shop.user_id == user.id))
    if shop is None:
        return []
    query = select(Order).where(Order.shop_id == shop.id, Order.status != "pending_payment").order_by(Order.id.desc()).limit(100)
    if status:
        query = query.where(Order.status == status)
    return [order_out(db, o, user, "seller") for o in db.scalars(query)]


@router.get("/orders/{public_id}", response_model=OrderOut)
def get_order(public_id: str, user: CurrentUser, db: DB) -> OrderOut:
    order, role = load(db, user, public_id)
    return order_out(db, order, user, role)


@router.post("/orders/{public_id}/pay", response_model=PayOut, dependencies=[Depends(rate_limit("pay", 20, 3600))])
def pay(public_id: str, user: CurrentUser, db: DB) -> PayOut:
    order, role = load(db, user, public_id)
    if role != "buyer":
        raise HTTPException(403, "Only the buyer can pay.")
    payment = service.start_payment(db, order, user, f"{get_settings().web_url}/checkout/{order.public_id}/result")
    db.commit()
    return PayOut(checkout_url=payment.checkout_url, reference=payment.reference, provider=payment.provider)


@router.get("/orders/{public_id}/payment-status", response_model=OrderOut)
def payment_status(public_id: str, user: CurrentUser, db: DB, reference: str | None = None) -> OrderOut:
    """Called when the buyer returns from checkout. Verifies the transaction with the provider; safe to call repeatedly."""
    order, role = load(db, user, public_id)
    if role == "buyer" and order.status == "pending_payment":
        query = select(Payment).where(Payment.order_id == order.id)
        if reference:
            query = query.where(Payment.reference == reference)
        payment = db.scalar(query.order_by(Payment.id.desc()))
        if payment is not None and payment.status == "initiated":
            service.verify_and_apply(db, payment)
            db.commit()
    return order_out(db, order, user, role)


@router.post("/orders/offline", response_model=OrderOut, status_code=201)
def record_offline(body: OfflineDealIn, user: CurrentUser, db: DB) -> OrderOut:
    """A cash or direct transfer deal both people record. Marked Not protected: no refunds or disputes."""
    convo = db.get(Conversation, body.conversation_id)
    if convo is None or user.id not in (convo.buyer_id, convo.seller_user_id) or convo.listing_id is None:
        raise HTTPException(404, "Conversation not found.")
    listing = db.get(Listing, convo.listing_id)
    shop = db.scalar(select(Shop).where(Shop.user_id == convo.seller_user_id))
    if listing is None or shop is None:
        raise HTTPException(409, "This listing is no longer available.")
    from app.ids import next_public_id

    total = body.agreed_price_kobo * body.quantity
    order = Order(
        public_id=next_public_id(db, "O"), buyer_id=convo.buyer_id, shop_id=shop.id, listing_id=listing.id, conversation_id=convo.id, status="accepted",
        listing_title=listing.title, listing_type=listing.type, quantity=body.quantity, unit_price_kobo=body.agreed_price_kobo, item_paid_kobo=total,
        buyer_total_kobo=total, commission_bps=0, commission_kobo=0, seller_amount_kobo=total, protected=False, payment_method="offline",
        note=body.note, offline_confirmed_by=[user.id], accepted_at=utcnow(),
    )  # fmt: skip
    db.add(order)
    db.flush()
    db.add(
        OrderEvent(order_id=order.id, actor_id=user.id, from_status="", to_status="accepted", note="Offline deal recorded (not protected)")
    )
    other = convo.seller_user_id if user.id == convo.buyer_id else convo.buyer_id
    notify(
        db,
        other,
        "order.new",
        f"Confirm your cash deal {order.public_id}",
        "Not protected: cash and transfers cannot be refunded by Campus Plug.",
        f"/orders/{order.public_id}" if other == convo.buyer_id else f"/seller/orders/{order.public_id}",
    )
    db.commit()
    return order_out(db, order, user, "buyer" if user.id == convo.buyer_id else "seller")


@router.post("/orders/{public_id}/confirm-offline", response_model=OrderOut)
def confirm_offline(public_id: str, user: CurrentUser, db: DB) -> OrderOut:
    order, role = load(db, user, public_id)
    if order.payment_method != "offline" or order.status != "accepted" or role not in ("buyer", "seller"):
        raise HTTPException(409, "There is nothing to confirm.")
    confirmed = list(order.offline_confirmed_by or [])
    if user.id not in confirmed:
        confirmed.append(user.id)
    order.offline_confirmed_by = confirmed
    shop = db.get(Shop, order.shop_id)
    if shop is not None and {order.buyer_id, shop.user_id} <= set(confirmed):
        service.log_event(db, order, "delivered", user, "Both parties confirmed the cash deal")
        order.status, order.delivered_at = "delivered", utcnow()
        service.confirm(db, order, user, "Both parties confirmed the cash deal")
    db.commit()
    return order_out(db, order, user, role)


# ---- seller actions ---------------------------------------------------------------------------------------------------


def _seller_order(db: Session, user: User, public_id: str) -> Order:
    order, role = load(db, user, public_id)
    if role != "seller":
        raise HTTPException(403, "Only the seller can do this.")
    return order


@router.post("/orders/{public_id}/accept", response_model=OrderOut)
def accept(public_id: str, user: CurrentUser, db: DB) -> OrderOut:
    order = _seller_order(db, user, public_id)
    service.accept(db, order, user)
    db.commit()
    return order_out(db, order, user, "seller")


@router.post("/orders/{public_id}/decline", response_model=OrderOut)
def decline(public_id: str, body: CancelIn, user: CurrentUser, db: DB) -> OrderOut:
    order = _seller_order(db, user, public_id)
    if order.status != "paid":
        raise HTTPException(409, "Only new paid orders can be declined.")
    service.cancel(db, order, user, body.reason or "Declined by the seller")
    db.commit()
    return order_out(db, order, user, "seller")


@router.post("/orders/{public_id}/stage", response_model=OrderOut)
def stage(public_id: str, body: StageIn, user: CurrentUser, db: DB) -> OrderOut:
    order = _seller_order(db, user, public_id)
    service.set_stage(db, order, body.stage, user)
    db.commit()
    return order_out(db, order, user, "seller")


@router.post("/orders/{public_id}/no-show", response_model=OrderOut)
def seller_reports_no_show(public_id: str, user: CurrentUser, db: DB) -> OrderOut:
    order = _seller_order(db, user, public_id)
    if order.listing_type != "service" or order.booking_at is None or order.booking_at > utcnow():
        raise HTTPException(409, "You can report a no-show after the booking time has passed.")
    service.transition(db, order, "disputed", user, "Seller reported the buyer did not show up")
    order.auto_confirm_at = None
    from app.ids import next_public_id

    dispute = Dispute(
        public_id=next_public_id(db, "D"),
        order_id=order.id,
        opened_by=user.id,
        reason="no_show",
        details="The seller reports the buyer did not show up.",
    )
    dispute.response_due_at = utcnow() + timedelta(hours=get_setting(db, "dispute_response_hours"))
    db.add(dispute)
    notify(
        db,
        order.buyer_id,
        "dispute.opened",
        f"No-show reported on {order.public_id}",
        "If this is wrong, explain what happened.",
        f"/orders/{order.public_id}",
    )
    db.commit()
    return order_out(db, order, user, "seller")


# ---- buyer actions ----------------------------------------------------------------------------------------------------


@router.post("/orders/{public_id}/confirm", response_model=OrderOut)
def confirm(public_id: str, user: CurrentUser, db: DB) -> OrderOut:
    order, role = load(db, user, public_id)
    if role != "buyer":
        raise HTTPException(403, "Only the buyer can confirm delivery.")
    if order.payment_method != "app":
        raise HTTPException(409, "Use the cash deal confirmation for this order.")
    service.confirm(db, order, user)
    db.commit()
    return order_out(db, order, user, "buyer")


@router.post("/orders/{public_id}/cancel", response_model=OrderOut)
def cancel(public_id: str, body: CancelIn, user: CurrentUser, db: DB) -> OrderOut:
    order, role = load(db, user, public_id)
    if role not in ("buyer", "seller"):
        raise HTTPException(403, "You cannot cancel this order.")
    if "cancel" not in _actions(db, order, role):
        raise HTTPException(409, "This order can no longer be cancelled here. Report a problem instead.")
    service.cancel(db, order, user, body.reason or f"Cancelled by the {role}")
    db.commit()
    return order_out(db, order, user, role)


@router.post("/orders/{public_id}/problem", response_model=OrderOut)
def problem(public_id: str, body: ProblemIn, user: CurrentUser, db: DB) -> OrderOut:
    order, role = load(db, user, public_id)
    if role != "buyer":
        raise HTTPException(403, "Only the buyer can report a problem.")
    disputes.open_dispute(db, order, user, body.reason, body.details)
    db.commit()
    return order_out(db, order, user, "buyer")


def _dispute_for(db: Session, user: User, public_id: str) -> tuple[Dispute, Order, str]:
    dispute = db.scalar(select(Dispute).where(Dispute.public_id == public_id.upper()))
    order = db.get(Order, dispute.order_id) if dispute else None
    role = role_in(db, user, order) if order else None
    if dispute is None or order is None or role is None:
        raise HTTPException(404, "Dispute not found.")
    return dispute, order, role


@router.post("/disputes/{public_id}/respond", response_model=OrderOut)
def respond(public_id: str, body: RespondIn, user: CurrentUser, db: DB) -> OrderOut:
    dispute, order, role = _dispute_for(db, user, public_id)
    if role != "seller":
        raise HTTPException(403, "Only the seller can respond.")
    disputes.seller_respond(db, dispute, order, user, body.message)
    db.commit()
    return order_out(db, order, user, role)


@router.post("/disputes/{public_id}/evidence", response_model=OrderOut)
async def evidence(
    public_id: str,
    user: CurrentUser,
    db: DB,
    note: Annotated[str, Form(max_length=1000)] = "",
    file: Annotated[UploadFile | None, File()] = None,
) -> OrderOut:
    dispute, order, role = _dispute_for(db, user, public_id)
    if role not in ("buyer", "seller") or dispute.status == "resolved":
        raise HTTPException(409, "You cannot add evidence to this dispute.")
    path = None
    if file is not None:
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "That image is too large (5 MB maximum).")
        sniff_image(data)
        path = get_storage().save_private(data, sniff_image(data)[0])
    if not note.strip() and path is None:
        raise HTTPException(422, "Add a note or a photo.")
    disputes.add_evidence(dispute, role, note.strip(), path)
    db.commit()
    return order_out(db, order, user, role)


@router.get("/files/evidence/{token}", include_in_schema=False)
def evidence_file(token: str, db: DB) -> Response:
    """Dispute photos are private: short-lived links only."""
    import jwt

    try:
        claims = decode_local_token(token)
    except jwt.PyJWTError:
        raise HTTPException(404, "This link has expired.") from None
    if claims.get("purpose") != "file" or "dispute" not in claims:
        raise HTTPException(404, "This link has expired.")
    data = get_storage().read_private(claims["path"])
    _, mime = sniff_image(data)
    return Response(data, media_type=mime, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


# ---- webhooks ---------------------------------------------------------------------------------------------------------


def process_webhook(db: Session, provider_name: str, raw: bytes, signature: str | None) -> dict[str, str]:
    """Verifies the signature, ignores repeats of the same event, and confirms the transaction with the provider before updating anything."""
    provider = get_provider()
    if provider.name != provider_name:
        raise HTTPException(404, "Unknown provider")
    if not provider.verify_signature(raw, signature):
        raise HTTPException(401, "Invalid signature")
    event = provider.parse_event(raw)
    if event is None:
        return {"status": "ignored"}
    try:
        db.add(WebhookEvent(provider=provider.name, event_key=event.key))
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    outcome = "ignored"
    if event.type in ("charge.success", "charge.failed"):
        payment = db.scalar(select(Payment).where(Payment.reference == event.reference))
        purchase = db.scalar(select(Purchase).where(Purchase.reference == event.reference)) if payment is None else None
        if payment is not None:
            outcome = service.verify_and_apply(db, payment)
        elif purchase is not None:
            outcome = purchases.apply(db, purchase, provider.verify(purchase.reference))
    db.commit()
    return {"status": outcome}


@router.post("/webhooks/{provider_name}", include_in_schema=False)
async def webhook(provider_name: str, request: Request, db: DB) -> dict[str, str]:
    raw = await request.body()
    return process_webhook(db, provider_name, raw, request.headers.get("x-paystack-signature"))


@router.post("/payments/local/complete", include_in_schema=False)
def local_complete(body: dict[str, str], db: DB, user: CurrentUser) -> dict[str, str]:
    """TEST ONLY: simulates the customer finishing the local checkout page, delivering a signed webhook through the real code path."""
    settings = get_settings()
    provider = get_provider()
    if not isinstance(provider, LocalProvider) or settings.is_production:
        raise HTTPException(404, "Not found")
    reference = body.get("reference", "")
    payment = db.scalar(select(Payment).where(Payment.reference == reference))
    order = db.get(Order, payment.order_id) if payment else None
    if payment is not None and order is not None and order.buyer_id == user.id:
        raw = provider.complete(reference, body.get("outcome") == "success")
        return {"order": order.public_id, **process_webhook(db, "local", raw, provider.sign(raw))}
    purchase = db.scalar(select(Purchase).where(Purchase.reference == reference))
    shop = db.get(Shop, purchase.shop_id) if purchase else None
    if purchase is None or shop is None or shop.user_id != user.id:
        raise HTTPException(404, "Payment not found")
    raw = provider.complete(reference, body.get("outcome") == "success")
    return {"order": "", **process_webhook(db, "local", raw, provider.sign(raw))}


# ---- seller earnings --------------------------------------------------------------------------------------------------


@router.get("/seller/earnings", response_model=EarningsOut)
def earnings(user: SellerUser, db: DB) -> EarningsOut:
    shop = db.scalar(select(Shop).where(Shop.user_id == user.id))
    if shop is None:
        raise HTTPException(404, "You have not created a shop yet.")
    done = ("confirmed", "paid_out")
    orders = list(db.scalars(select(Order).where(Order.shop_id == shop.id, Order.protected.is_(True))))
    sold = [o for o in orders if o.status in done]
    held = [o for o in orders if o.status in service.HELD_STATUSES]
    payouts = list(db.scalars(select(Payout).where(Payout.shop_id == shop.id).order_by(Payout.id.desc()).limit(50)))

    def total(status: tuple[str, ...]) -> int:
        return sum(p.amount_kobo for p in payouts if p.status in status)

    return EarningsOut(
        gross_sales_kobo=sum(o.unit_price_kobo * o.quantity for o in sold),
        discounts_kobo=sum(o.seller_discount_kobo for o in sold),
        commission_kobo=sum(o.commission_kobo - o.commission_returned_kobo for o in sold),
        net_earnings_kobo=sum(service.payable_to_seller(o) for o in sold),
        held_kobo=sum(service.payable_to_seller(o) for o in held if not o.funds_released),
        processing_payouts_kobo=total(("pending", "processing", "held")),
        paid_payouts_kobo=total(("paid",)),
        unverified=shop.verification_status != "verified",
        payout_review_required=shop.payout_review_required,
        payouts=[
            {
                "order": next((o.public_id for o in orders if o.id == p.order_id), ""),
                "amount_kobo": p.amount_kobo,
                "status": p.status,
                "hold_reason": p.hold_reason,
                "created_at": p.created_at.isoformat(),
            }
            for p in payouts
        ],
    )


@router.get("/banks")
def banks() -> list[str]:
    return sorted(BANKS)
