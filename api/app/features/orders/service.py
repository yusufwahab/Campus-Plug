import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.payments import Recipient, VerifyResult, get_provider
from app.db import utcnow
from app.features.orders import ledger
from app.features.verification.service import recompute_trust
from app.ids import next_public_id
from app.jobs.core import enqueue
from app.models.catalogue import Category, Listing, Shop
from app.models.commerce import Order, OrderEvent, Payment, Payout, Refund
from app.models.identity import User
from app.models.social import Conversation, Message
from app.money import OrderAmounts, compute_order_amounts, resolve_commission_bps, split_refund
from app.notify import notify
from app.settings_store import get_setting

# Allowed status changes. Anything else is rejected by the backend, whoever asks.
TRANSITIONS: dict[str, set[str]] = {
    "pending_payment": {"paid", "cancelled"},
    "paid": {"accepted", "cancelled"},
    "accepted": {"preparing", "ready", "cancelled", "disputed"},
    "preparing": {"ready", "cancelled", "disputed"},
    "ready": {"delivered", "cancelled", "disputed"},
    "delivered": {"confirmed", "disputed"},
    "confirmed": {"paid_out"},
    "disputed": {"refunded", "confirmed"},
    "paid_out": set(),
    "cancelled": set(),
    "refunded": set(),
}
OPEN_STATUSES = ("pending_payment", "paid", "accepted", "preparing", "ready", "delivered", "disputed")
HELD_STATUSES = ("paid", "accepted", "preparing", "ready", "delivered", "disputed")


def log_event(db: Session, order: Order, to: str, actor: User | None, note: str = "") -> None:
    db.add(OrderEvent(order_id=order.id, actor_id=actor.id if actor else None, from_status=order.status, to_status=to, note=note[:300]))


def transition(db: Session, order: Order, to: str, actor: User | None, note: str = "") -> None:
    if to not in TRANSITIONS.get(order.status, set()):
        raise HTTPException(409, f"This order cannot move from {order.status.replace('_', ' ')} to {to.replace('_', ' ')}.")
    log_event(db, order, to, actor, note)
    order.status = to


def rate_for(db: Session, shop: Shop, category: Category) -> int:
    """Commission rate for a NEW order: seller override, then plan, then category, then the platform default."""
    from app.features.promotions.plans import plan_bps

    return resolve_commission_bps(
        default_bps=get_setting(db, "commission_bps"),
        category_bps=category.commission_override_bps,
        plan_bps=plan_bps(db, shop),
        seller_bps=shop.commission_override_bps,
    )


def create_order(
    db: Session,
    *,
    buyer: User,
    listing: Listing,
    quantity: int = 1,
    fulfilment: str = "pickup",
    booking_at: datetime | None = None,
    agreed_unit_price_kobo: int | None = None,
    agreed_delivery_fee_kobo: int | None = None,
    conversation_id: int | None = None,
    request_message_id: int | None = None,
    note: str = "",
    seller_discount_kobo: int = 0,
    platform_discount_kobo: int = 0,
    promo_code_id: int | None = None,
) -> Order:
    shop = db.get(Shop, listing.shop_id)
    category = db.get(Category, listing.category_id)
    if shop is None or category is None or listing.status != "active" or listing.deleted_at is not None:
        raise HTTPException(409, "This listing is no longer available.")
    if shop.user_id == buyer.id:
        raise HTTPException(422, "You cannot buy your own listing.")
    if shop.holiday_mode:
        raise HTTPException(409, "This shop is on holiday.")
    if shop.verification_status != "verified":
        raise HTTPException(
            403, "This seller is not verified yet, so in-app payment is not available. Ask them to verify, or agree a cash deal."
        )
    if shop.payout_review_required:
        raise HTTPException(403, "This seller's payout details are under review.")
    if listing.type == "product" and not listing.preorder and listing.quantity < quantity:
        raise HTTPException(409, "There is not enough stock for that quantity.")
    if fulfilment not in ("pickup", "delivery") or (listing.fulfilment != "both" and fulfilment != listing.fulfilment):
        raise HTTPException(422, "That collection option is not offered for this listing.")
    if listing.type == "service" and (booking_at is None or booking_at <= utcnow()):
        raise HTTPException(422, "Choose a booking time in the future.")
    if conversation_id is None:
        # Link the order to the buyer's existing chat with this seller about this listing, if there is one.
        conversation_id = db.scalar(
            select(Conversation.id).where(
                Conversation.buyer_id == buyer.id, Conversation.seller_user_id == shop.user_id, Conversation.listing_id == listing.id
            )
        )
    unit = agreed_unit_price_kobo if agreed_unit_price_kobo is not None else listing.price_kobo
    deposit_only = listing.type == "service" and listing.deposit_kobo is not None
    if deposit_only:
        unit, quantity = listing.deposit_kobo or unit, 1
    delivery = 0
    if fulfilment == "delivery":
        delivery = agreed_delivery_fee_kobo if agreed_delivery_fee_kobo is not None else listing.delivery_fee_kobo
    absorbed = bool(get_setting(db, "provider_fee_absorbed"))
    try:
        amounts = compute_order_amounts(
            unit_price_kobo=unit,
            quantity=quantity,
            seller_discount_kobo=seller_discount_kobo,
            platform_discount_kobo=platform_discount_kobo,
            delivery_fee_kobo=delivery,
            commission_bps=rate_for(db, shop, category),
            provider_fee_absorbed=absorbed,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    order = Order(
        public_id=next_public_id(db, "O"),
        buyer_id=buyer.id,
        shop_id=shop.id,
        listing_id=listing.id,
        conversation_id=conversation_id,
        request_message_id=request_message_id,
        listing_title=listing.title,
        listing_type=listing.type,
        quantity=amounts.quantity,
        unit_price_kobo=amounts.unit_price_kobo,
        seller_discount_kobo=amounts.seller_discount_kobo,
        platform_discount_kobo=amounts.platform_discount_kobo,
        item_paid_kobo=amounts.item_paid_kobo,
        delivery_fee_kobo=amounts.delivery_fee_kobo,
        buyer_total_kobo=amounts.buyer_total_kobo,
        commission_bps=amounts.commission_bps,
        commission_kobo=amounts.commission_kobo,
        seller_amount_kobo=amounts.seller_amount_kobo,
        provider_fee_absorbed=absorbed,
        instant_split=bool(get_setting(db, "instant_split")),
        fulfilment=fulfilment,
        booking_at=booking_at,
        deposit_only=deposit_only,
        note=note[:300],
        promo_code_id=promo_code_id,
    )
    db.add(order)
    db.flush()
    db.add(OrderEvent(order_id=order.id, actor_id=buyer.id, from_status="", to_status="pending_payment", note="Order created"))
    return order


def amounts_of(order: Order) -> OrderAmounts:
    return OrderAmounts(
        unit_price_kobo=order.unit_price_kobo,
        quantity=order.quantity,
        seller_discount_kobo=order.seller_discount_kobo,
        platform_discount_kobo=order.platform_discount_kobo,
        item_paid_kobo=order.item_paid_kobo,
        delivery_fee_kobo=order.delivery_fee_kobo,
        buyer_total_kobo=order.buyer_total_kobo,
        commission_bps=order.commission_bps,
        commission_kobo=order.commission_kobo,
        seller_amount_kobo=order.seller_amount_kobo,
        provider_fee_kobo=order.provider_fee_kobo,
        platform_net_kobo=0,
    )


def payable_to_seller(order: Order) -> int:
    """What the seller finally receives: item price less commission (reduced by any refund) plus delivery, less provider fee if the seller bears it."""
    commission_kept = order.commission_kobo - order.commission_returned_kobo
    fee = 0 if order.provider_fee_absorbed else order.provider_fee_kobo
    return order.item_paid_kobo - order.refunded_item_kobo - commission_kept + order.delivery_fee_kobo - fee


# ---- payment ----------------------------------------------------------------------------------------------------------


def start_payment(db: Session, order: Order, buyer: User, callback_url: str) -> Payment:
    if order.status != "pending_payment":
        raise HTTPException(409, "This order is not waiting for payment.")
    existing = db.scalar(select(Payment).where(Payment.order_id == order.id, Payment.status == "initiated").order_by(Payment.id.desc()))
    if existing is not None and existing.checkout_url:
        return existing
    provider = get_provider()
    reference = f"CPO-{order.public_id.removeprefix('CP-O-')}-{secrets.token_hex(4)}"
    result = provider.initialize(reference=reference, amount_kobo=order.buyer_total_kobo, email=buyer.email, callback_url=callback_url)
    payment = Payment(
        order_id=order.id, provider=provider.name, reference=reference, amount_kobo=order.buyer_total_kobo, checkout_url=result.checkout_url
    )
    db.add(payment)
    db.flush()
    return payment


def apply_payment(db: Session, payment: Payment, result: VerifyResult) -> str:
    """Records the outcome of a verified transaction. Safe to call any number of times for the same payment.

    Returns: applied | already_processed | pending | failed | mismatch
    """
    order = db.get(Order, payment.order_id)
    if order is None:
        return "mismatch"
    if payment.status == "success":
        return "already_processed"
    if result.status == "failed":
        payment.status = "failed"
        return "failed"
    if result.status != "success":
        return "pending"
    if result.amount_kobo != order.buyer_total_kobo or result.currency != "NGN":
        # Never trust the webhook alone: the verified amount must equal what the order says the buyer owes.
        payment.status = "failed"
        return "mismatch"
    if order.status != "pending_payment":
        # Paid after the order was cancelled: money must go back to the buyer.
        payment.status, payment.paid_at, payment.fee_kobo = "success", utcnow(), result.fee_kobo
        cash = order.buyer_total_kobo
        ledger.post(
            db,
            order=order,
            kind="payment_received",
            legs=[(ledger.PROVIDER_CLEARING, cash - result.fee_kobo), (ledger.PROVIDER_FEES, result.fee_kobo), (ledger.ESCROW, -cash)],
            ref=payment.reference,
        )
        _refund_cash(db, order, payment, cash, "Payment arrived after the order was cancelled")
        return "already_processed"
    payment.status, payment.paid_at, payment.fee_kobo = "success", utcnow(), result.fee_kobo
    order.provider_fee_kobo = result.fee_kobo
    if not order.provider_fee_absorbed:
        order.seller_amount_kobo = payable_to_seller(order)
    transition(db, order, "paid", None, "Payment confirmed")
    now = utcnow()
    order.paid_at = now
    order.accept_by = now + timedelta(hours=get_setting(db, "seller_accept_hours"))
    cash = order.buyer_total_kobo
    ledger.post(
        db,
        order=order,
        kind="payment_received",
        legs=[(ledger.PROVIDER_CLEARING, cash - result.fee_kobo), (ledger.PROVIDER_FEES, result.fee_kobo), (ledger.ESCROW, -cash)],
        ref=payment.reference,
    )
    if order.platform_discount_kobo:
        ledger.post(
            db,
            order=order,
            kind="promo_funding",
            legs=[(ledger.PROMO_COST, order.platform_discount_kobo), (ledger.ESCROW, -order.platform_discount_kobo)],
        )
    listing = db.get(Listing, order.listing_id)
    if listing is not None and listing.type == "product" and not listing.preorder:
        listing.quantity = max(listing.quantity - order.quantity, 0)
        if listing.quantity == 0:
            listing.status = "sold_out"
    if order.conversation_id:
        convo = db.get(Conversation, order.conversation_id)
        if convo is not None:
            convo.phone_unlocked_by_payment = True  # phone numbers unlock once the buyer has paid
    if order.request_message_id:
        msg = db.get(Message, order.request_message_id)
        if msg is not None:
            msg.payload = {**(msg.payload or {}), "status": "paid", "order_id": order.public_id}
    shop = db.get(Shop, order.shop_id)
    if shop is not None:
        notify(
            db,
            shop.user_id,
            "order.new",
            f"New paid order {order.public_id}",
            f"{order.listing_title} x{order.quantity}. Accept it within {get_setting(db, 'seller_accept_hours')} hours.",
            f"/seller/orders/{order.public_id}",
        )
    notify(
        db,
        order.buyer_id,
        "payment.received",
        f"Payment received for {order.public_id}",
        "Your money is held safely until you confirm delivery.",
        f"/orders/{order.public_id}",
    )
    if order.instant_split:
        order.auto_confirm_at = None
        _release(db, order, instant=True)
    return "applied"


def verify_and_apply(db: Session, payment: Payment) -> str:
    result = get_provider().verify(payment.reference)
    return apply_payment(db, payment, result)


# ---- fulfilment ------------------------------------------------------------------------------------------------------


def accept(db: Session, order: Order, seller: User) -> None:
    transition(db, order, "accepted", seller)
    order.accepted_at = utcnow()
    notify(
        db,
        order.buyer_id,
        "order.accepted",
        f"{order.public_id} accepted",
        "The seller is preparing your order.",
        f"/orders/{order.public_id}",
    )


def set_stage(db: Session, order: Order, to: str, seller: User) -> None:
    if to not in ("preparing", "ready", "delivered"):
        raise HTTPException(422, "Unknown stage.")
    if order.status == "paid":
        raise HTTPException(409, "Accept the order first.")
    transition(db, order, to, seller)
    if to == "delivered":
        now = utcnow()
        order.delivered_at = now
        order.auto_confirm_at = now + timedelta(hours=get_setting(db, "buyer_confirm_hours"))
        notify(
            db,
            order.buyer_id,
            "order.status",
            f"{order.public_id} delivered",
            f"Confirm you got it within {get_setting(db, 'buyer_confirm_hours')} hours or it confirms automatically.",
            f"/orders/{order.public_id}",
        )
    else:
        notify(
            db,
            order.buyer_id,
            "order.status",
            f"{order.public_id} is {'ready or on its way' if to == 'ready' else 'being prepared'}",
            order.listing_title,
            f"/orders/{order.public_id}",
        )


def _refund_cash(db: Session, order: Order, payment: Payment, cash_kobo: int, reason: str) -> Refund:
    """Sends money back to the buyer through the provider and records it in the ledger."""
    refund = Refund(order_id=order.id, amount_kobo=cash_kobo, reason=reason[:300])
    db.add(refund)
    result = get_provider().refund(reference=payment.reference, amount_kobo=cash_kobo)
    refund.status = "done" if result.status == "success" else "pending"
    refund.provider_ref = result.provider_ref
    ledger.post(
        db, order=order, kind="refund", legs=[(ledger.PROVIDER_CLEARING, -cash_kobo), (ledger.ESCROW, cash_kobo)], ref=payment.reference
    )
    if refund.status == "done":
        payment.status = "refunded" if cash_kobo >= payment.amount_kobo else payment.status
    return refund


def _paid_payment(db: Session, order: Order) -> Payment | None:
    return db.scalar(
        select(Payment).where(Payment.order_id == order.id, Payment.status.in_(("success", "refunded"))).order_by(Payment.id.desc())
    )


def cancel(db: Session, order: Order, actor: User | None, reason: str) -> None:
    """Cancels an order. If the buyer already paid they get everything back, including the commission, and stock is restored."""
    paid = order.status != "pending_payment"
    from app.features.promotions.promos import release

    release(db, order)
    transition(db, order, "cancelled", actor, reason)
    order.cancelled_at = utcnow()
    order.cancel_reason = reason[:300]
    if paid:
        payment = _paid_payment(db, order)
        if payment is not None:
            if order.platform_discount_kobo:
                ledger.post(
                    db,
                    order=order,
                    kind="promo_reversal",
                    legs=[(ledger.ESCROW, order.platform_discount_kobo), (ledger.PROMO_COST, -order.platform_discount_kobo)],
                )
            _refund_cash(db, order, payment, order.buyer_total_kobo, reason or "Order cancelled")
        listing = db.get(Listing, order.listing_id)
        if listing is not None and listing.type == "product" and not listing.preorder:
            listing.quantity += order.quantity
            if listing.status == "sold_out":
                listing.status = "active"
    notify(
        db,
        order.buyer_id,
        "order.cancelled",
        f"{order.public_id} cancelled",
        ("Your payment is being refunded. " if paid else "") + (reason or ""),
        f"/orders/{order.public_id}",
    )
    shop = db.get(Shop, order.shop_id)
    if shop is not None:
        notify(db, shop.user_id, "order.cancelled", f"{order.public_id} cancelled", reason or "", f"/seller/orders/{order.public_id}")


# ---- confirmation, release and payout ----------------------------------------------------------------------------------


def confirm(db: Session, order: Order, actor: User | None, note: str = "Buyer confirmed delivery", *, count_deal: bool = True) -> None:
    transition(db, order, "confirmed", actor, note)
    order.confirmed_at = utcnow()
    shop = db.get(Shop, order.shop_id)
    if shop is not None and count_deal:
        shop.confirmed_deals += 1
        recompute_trust(db, shop)
    if order.payment_method == "app" and not order.funds_released:
        _release(db, order, instant=False)


def _release(db: Session, order: Order, *, instant: bool) -> None:
    """Moves held money to the seller and records the platform's commission, then queues the payout."""
    held = order.item_paid_kobo - order.refunded_item_kobo + order.delivery_fee_kobo
    commission_kept = order.commission_kobo - order.commission_returned_kobo
    seller_amount = payable_to_seller(order)
    legs = [(ledger.ESCROW, held), (ledger.SELLER_PAYABLE, -seller_amount), (ledger.PLATFORM_REVENUE, -commission_kept)]
    if not order.provider_fee_absorbed:
        legs.append((ledger.PROVIDER_FEES, -order.provider_fee_kobo))
    ledger.post(db, order=order, kind="release", legs=legs)
    order.funds_released = True
    shop = db.get(Shop, order.shop_id)
    payout = Payout(order_id=order.id, shop_id=order.shop_id, amount_kobo=seller_amount)
    if shop is None or not shop.payout_account_number or shop.payout_review_required:
        payout.status = "held"
        payout.hold_reason = "Payout details are missing or under review"
    db.add(payout)
    db.flush()
    if payout.status == "pending":
        enqueue(db, "process_payout", {"payout_id": payout.id})
    elif shop is not None:
        notify(
            db,
            shop.user_id,
            "payout.held",
            f"Payout held for {order.public_id}",
            "Add or confirm your payout details and we will send it.",
            "/seller/settings",
        )
    if instant:
        order.status = "confirmed"
        log_event(db, order, "confirmed", None, "Instant split: seller paid at payment time")


def process_payout(db: Session, payout: Payout) -> None:
    """Pays the seller through the provider adapter. Raises on failure so the job runner retries with backoff."""
    if payout.status in ("paid", "held"):
        return
    order = db.get(Order, payout.order_id)
    shop = db.get(Shop, payout.shop_id)
    if order is None or shop is None:
        return
    if order.status == "disputed":
        payout.status, payout.hold_reason = "held", "Order is under dispute"
        return
    if not shop.payout_account_number or shop.payout_review_required:
        payout.status, payout.hold_reason = "held", "Payout details are missing or under review"
        return
    payout.status = "processing"
    result = get_provider().transfer(
        recipient=Recipient(shop.payout_bank or "", shop.payout_account_number, shop.payout_account_name or shop.name),
        amount_kobo=payout.amount_kobo,
        reference=f"{order.public_id}-payout-{payout.id}",
    )
    payout.provider_ref = result.provider_ref
    if result.status == "success":
        payout.status, payout.paid_at = "paid", utcnow()
        ledger.post(
            db,
            order=order,
            kind="payout",
            legs=[(ledger.SELLER_PAYABLE, payout.amount_kobo), (ledger.PROVIDER_CLEARING, -payout.amount_kobo)],
            ref=payout.provider_ref,
        )
        if order.status == "confirmed":
            log_event(db, order, "paid_out", None, "Payout sent")
            order.status = "paid_out"
        notify(
            db, shop.user_id, "payout.sent", f"Payout sent for {order.public_id}", "It should reach your bank shortly.", "/seller/earnings"
        )


# ---- refunds from disputes --------------------------------------------------------------------------------------------


def refund_item_amount(db: Session, order: Order, refund_item_kobo: int, reason: str) -> None:
    """Refunds part (or all) of the item price while funds are still held. A full refund returns the commission; a partial refund returns it proportionally."""
    split = split_refund(amounts_of(order), refund_item_kobo, include_delivery=refund_item_kobo == order.item_paid_kobo)
    payment = _paid_payment(db, order)
    if payment is None:
        raise HTTPException(409, "There is no payment to refund.")
    full = refund_item_kobo == order.item_paid_kobo
    promo_share = order.platform_discount_kobo * refund_item_kobo // order.item_paid_kobo if order.item_paid_kobo else 0
    cash = refund_item_kobo - promo_share + (order.delivery_fee_kobo if full else 0)
    if order.funds_released:
        # Instant-split fallback: the seller was already paid, so the platform refunds from its own funds.
        refund = Refund(order_id=order.id, amount_kobo=cash, commission_returned_kobo=split.commission_returned_kobo, reason=reason[:300])
        db.add(refund)
        result = get_provider().refund(reference=payment.reference, amount_kobo=cash)
        refund.status, refund.provider_ref = ("done" if result.status == "success" else "pending"), result.provider_ref
        ledger.post(db, order=order, kind="refund_from_platform", legs=[(ledger.PROVIDER_CLEARING, -cash), (ledger.PLATFORM_REVENUE, cash)])
    else:
        if promo_share:
            ledger.post(db, order=order, kind="promo_reversal", legs=[(ledger.ESCROW, promo_share), (ledger.PROMO_COST, -promo_share)])
        refund = _refund_cash(db, order, payment, cash, reason)
        refund.commission_returned_kobo = split.commission_returned_kobo
    order.refunded_item_kobo += refund_item_kobo
    order.commission_returned_kobo += split.commission_returned_kobo
    if full:
        listing = db.get(Listing, order.listing_id)
        if listing is not None and listing.type == "product" and not listing.preorder:
            listing.quantity += order.quantity
            if listing.status == "sold_out":
                listing.status = "active"
