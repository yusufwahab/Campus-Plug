from datetime import timedelta

import pytest
from sqlalchemy import func, select

import app.jobs.handlers  # noqa: F401  (registers scheduled handlers)
import app.jobs.orders  # noqa: F401
import app.notify  # noqa: F401
from app.adapters.payments import LocalProvider
from app.db import utcnow
from app.features.orders import ledger
from app.jobs.core import run_due
from app.models.catalogue import Category, Listing, Shop
from app.models.commerce import Dispute, LedgerEntry, Order, Payment, Payout, Refund, WebhookEvent
from app.models.identity import User
from app.models.social import Notification
from app.models.system import Setting
from tests.test_marketplace import category_id, listing_body, start_shop

API = "/api/v1"
NAIRA = 100


@pytest.fixture(autouse=True)
def _clean_local_provider():
    LocalProvider.transactions.clear()


class Trade:
    """A verified seller with a listing, a buyer, and a chat between them."""

    def __init__(self, client, h, db, *, price=10_000 * NAIRA, verified=True, payout=True, **listing_over):
        self.client, self.h, self.db = client, h, db
        self.seller_headers, _ = start_shop(client, h, "seller@example.com", "Trade Shop")
        shop = db.scalars(select(Shop)).one()
        if verified:
            shop.verification_status = "verified"
        if payout:
            shop.payout_bank, shop.payout_account_number, shop.payout_account_name = "GTBank", "0123456789", "Trade Shop"
        db.commit()
        fields = {"price_kobo": price, "quantity": 5, "fulfilment": "both", "delivery_fee_kobo": 500 * NAIRA, **listing_over}
        body = listing_body(db, **fields)
        self.listing = client.post(f"{API}/listings", json=body, headers=self.seller_headers).json()
        h.make_user("buyer@example.com", phone="+2348011111111")
        self.buyer_headers = h.login("buyer@example.com")
        self.convo = client.post(f"{API}/conversations", json={"listing_id": self.listing["public_id"]}, headers=self.buyer_headers).json()[
            "id"
        ]

    def order(self, **over):
        res = self.client.post(f"{API}/orders", json={"listing_id": self.listing["public_id"], **over}, headers=self.buyer_headers)
        assert res.status_code == 201, res.text
        return res.json()

    def pay(self, order_id, outcome="success"):
        started = self.client.post(f"{API}/orders/{order_id}/pay", headers=self.buyer_headers)
        assert started.status_code == 200, started.text
        done = self.client.post(
            f"{API}/payments/local/complete",
            json={"reference": started.json()["reference"], "outcome": outcome},
            headers=self.buyer_headers,
        )
        assert done.status_code == 200, done.text
        return started.json()["reference"], done.json()

    def get(self, order_id, who="buyer"):
        headers = self.buyer_headers if who == "buyer" else self.seller_headers
        return self.client.get(f"{API}/orders/{order_id}", headers=headers).json()

    def act(self, order_id, action, body=None, who="seller", expect=200):
        headers = self.seller_headers if who == "seller" else self.buyer_headers
        res = self.client.post(f"{API}/orders/{order_id}/{action}", json=body or {}, headers=headers)
        assert res.status_code == expect, f"{action}: {res.status_code} {res.text}"
        return res.json()

    def paid_order(self, **over):
        o = self.order(**over)
        self.pay(o["public_id"])
        return o["public_id"]

    def to_delivered(self, oid):
        self.act(oid, "accept")
        self.act(oid, "stage", {"stage": "preparing"})
        self.act(oid, "stage", {"stage": "ready"})
        self.act(oid, "stage", {"stage": "delivered"})


@pytest.fixture()
def trade(client, h, db):
    return Trade(client, h, db)


def admin(client, h, email="boss@example.com"):
    h.make_user(email, role="admin")
    return h.login(email)


def balances(db):
    return {
        a: ledger.balance(db, a)
        for a in (
            ledger.PROVIDER_CLEARING,
            ledger.ESCROW,
            ledger.SELLER_PAYABLE,
            ledger.PLATFORM_REVENUE,
            ledger.PROVIDER_FEES,
            ledger.PROMO_COST,
        )
    }


def assert_ledger_balanced(db):
    groups = db.execute(select(LedgerEntry.group_id, func.sum(LedgerEntry.amount_kobo)).group_by(LedgerEntry.group_id)).all()
    assert groups and all(total == 0 for _, total in groups), "every ledger movement must sum to zero"
    assert db.scalar(select(func.sum(LedgerEntry.amount_kobo))) == 0


# ---- creating orders: frozen amounts, worked examples -----------------------------------------------------------------


def test_order_amounts_follow_the_worked_example(trade):
    o = trade.order()
    assert o["status"] == "pending_payment" and o["public_id"].startswith("CP-O-")
    assert (o["item_paid_kobo"], o["buyer_total_kobo"], o["delivery_fee_kobo"]) == (10_000 * NAIRA, 10_000 * NAIRA, 0)


def test_seller_sees_commission_and_payout_but_buyer_never_does(trade):
    oid = trade.paid_order()
    buyer = trade.get(oid, "buyer")
    seller = trade.get(oid, "seller")
    assert buyer["commission_kobo"] is None and buyer["seller_amount_kobo"] is None and buyer["commission_bps"] is None
    assert (seller["commission_bps"], seller["commission_kobo"], seller["seller_amount_kobo"]) == (2000, 2_000 * NAIRA, 8_000 * NAIRA)


def test_delivery_fee_is_added_for_the_buyer_but_not_commissioned(trade):
    oid = trade.paid_order(fulfilment="delivery")
    seller = trade.get(oid, "seller")
    assert trade.get(oid)["buyer_total_kobo"] == 10_500 * NAIRA
    assert (seller["commission_kobo"], seller["seller_amount_kobo"]) == (2_000 * NAIRA, 8_500 * NAIRA)


def test_commission_rate_is_frozen_on_the_order_when_admin_changes_it(client, h, trade):
    first = trade.order()
    boss = admin(client, h)
    assert (
        client.put(f"{API}/admin/settings/commission_bps", json={"value": 1000, "reason": "Promo month"}, headers=boss).status_code == 200
    )
    second = trade.order()
    first_db = trade.db.scalars(select(Order).where(Order.public_id == first["public_id"])).one()
    second_db = trade.db.scalars(select(Order).where(Order.public_id == second["public_id"])).one()
    assert (first_db.commission_bps, first_db.commission_kobo, first_db.seller_amount_kobo) == (2000, 2_000 * NAIRA, 8_000 * NAIRA)
    assert (second_db.commission_bps, second_db.commission_kobo, second_db.seller_amount_kobo) == (1000, 1_000 * NAIRA, 9_000 * NAIRA)


def test_rate_precedence_for_new_orders_is_seller_then_category_then_default(client, h, trade, db):
    db.scalars(select(Category).where(Category.id == category_id(db))).one().commission_override_bps = 1500
    db.commit()
    by_category = trade.order()["public_id"]
    assert db.scalars(select(Order).where(Order.public_id == by_category)).one().commission_bps == 1500
    db.scalars(select(Shop)).one().commission_override_bps = 500
    db.commit()
    by_seller = trade.order()["public_id"]
    assert db.scalars(select(Order).where(Order.public_id == by_seller)).one().commission_bps == 500


def test_unverified_sellers_cannot_receive_in_app_orders(client, h, db):
    t = Trade(client, h, db, verified=False)
    res = client.post(f"{API}/orders", json={"listing_id": t.listing["public_id"]}, headers=t.buyer_headers)
    assert res.status_code == 403 and "not verified" in res.json()["detail"]


def test_cannot_buy_your_own_listing_or_without_stock_or_when_removed(client, h, db, trade):
    assert client.post(f"{API}/orders", json={"listing_id": trade.listing["public_id"]}, headers=trade.seller_headers).status_code == 422
    assert (
        client.post(
            f"{API}/orders", json={"listing_id": trade.listing["public_id"], "quantity": 99}, headers=trade.buyer_headers
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{API}/orders",
            json={"listing_id": trade.listing["public_id"], "fulfilment": "delivery", "quantity": 2},
            headers=trade.buyer_headers,
        ).status_code
        == 201
    )
    client.post(f"{API}/listings/{trade.listing['public_id']}/status", json={"status": "removed"}, headers=trade.seller_headers)
    assert client.post(f"{API}/orders", json={"listing_id": trade.listing["public_id"]}, headers=trade.buyer_headers).status_code in (
        404,
        409,
    )
    assert client.post(f"{API}/orders", json={}, headers=trade.buyer_headers).status_code == 422
    assert client.post(f"{API}/orders", json={"listing_id": "CP-P-1"}).status_code == 401


def test_order_from_a_chat_payment_request_uses_the_agreed_price_once(client, trade):
    sent = client.post(
        f"{API}/conversations/{trade.convo}/payment-request",
        json={"agreed_price_kobo": 9_000 * NAIRA, "quantity": 2, "delivery_fee_kobo": 300 * NAIRA},
        headers=trade.seller_headers,
    )
    mid = sent.json()["id"]
    assert (
        client.post(f"{API}/orders", json={"message_id": mid}, headers=trade.seller_headers).status_code == 404
    )  # only the buyer can open it
    first = client.post(f"{API}/orders", json={"message_id": mid}, headers=trade.buyer_headers).json()
    assert (
        first["quantity"],
        first["unit_price_kobo"],
        first["item_paid_kobo"],
        first["delivery_fee_kobo"],
        first["buyer_total_kobo"],
    ) == (2, 9_000 * NAIRA, 18_000 * NAIRA, 300 * NAIRA, 18_300 * NAIRA)
    assert (
        client.post(f"{API}/orders", json={"message_id": mid}, headers=trade.buyer_headers).json()["public_id"] == first["public_id"]
    )  # no duplicate order
    status = [
        m
        for m in client.get(f"{API}/conversations/{trade.convo}/messages", headers=trade.buyer_headers).json()
        if m["kind"] == "payment_request"
    ][0]["payload"]["status"]
    assert status == "ordered"


def test_unknown_promo_codes_are_rejected_not_ignored(trade):
    res = trade.client.post(
        f"{API}/orders", json={"listing_id": trade.listing["public_id"], "promo_code": "SAVE10"}, headers=trade.buyer_headers
    )
    assert res.status_code == 422


# ---- paying, webhooks and idempotency ----------------------------------------------------------------------------------


def test_payment_marks_order_paid_holds_funds_and_unlocks_phone(client, trade, db):
    o = trade.order()
    assert client.get(f"{API}/conversations/{trade.convo}", headers=trade.buyer_headers).json()["phone"] is None
    ref, result = trade.pay(o["public_id"])
    assert result["status"] == "applied"
    paid = trade.get(o["public_id"])
    assert paid["status"] == "paid" and paid["paid_at"] and paid["accept_by"]
    b = balances(db)
    assert b[ledger.ESCROW] == -10_000 * NAIRA  # money is held, not yet the seller's
    assert b[ledger.SELLER_PAYABLE] == 0 and b[ledger.PLATFORM_REVENUE] == 0
    assert b[ledger.PROVIDER_CLEARING] + b[ledger.PROVIDER_FEES] == 10_000 * NAIRA
    assert_ledger_balanced(db)
    assert db.scalars(select(Payment)).one().status == "success"
    # phone numbers unlock once the buyer has paid
    assert client.get(f"{API}/conversations/{trade.convo}", headers=trade.seller_headers).json()["phone"] == "+2348011111111"
    kinds_seller = [
        n.kind
        for n in db.scalars(select(Notification).join(User, User.id == Notification.user_id).where(User.email == "seller@example.com"))
    ]
    assert "order.new" in kinds_seller


def test_stock_is_reserved_when_paid_and_sold_out_at_zero(client, trade, db):
    trade.paid_order(quantity=4)
    assert db.get(Listing, 1).quantity == 1
    trade.paid_order(quantity=1)
    listing = db.get(Listing, 1)
    assert (listing.quantity, listing.status) == (0, "sold_out")


def test_failed_payment_leaves_the_order_waiting(trade, db):
    o = trade.order()
    _, result = trade.pay(o["public_id"], outcome="failed")
    assert result["status"] == "failed"
    assert trade.get(o["public_id"])["status"] == "pending_payment"
    assert db.query(LedgerEntry).count() == 0
    again = trade.client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers)
    assert again.status_code == 200 and again.json()["reference"]  # a retry starts a new attempt


def signed(provider, event, reference, event_id="evt-1"):
    import json

    raw = json.dumps({"event": event, "data": {"reference": reference, "id": event_id}}).encode()
    return raw, {"x-paystack-signature": provider.sign(raw), "content-type": "application/json"}


def test_webhook_rejects_bad_signatures_and_unknown_providers(client, trade):
    o = trade.order()
    started = client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers).json()
    provider = LocalProvider()
    raw, headers = signed(provider, "charge.success", started["reference"])
    assert client.post(f"{API}/webhooks/local", content=raw, headers={**headers, "x-paystack-signature": "0" * 128}).status_code == 401
    assert client.post(f"{API}/webhooks/local", content=raw, headers={"content-type": "application/json"}).status_code == 401
    assert client.post(f"{API}/webhooks/stripe", content=raw, headers=headers).status_code == 404
    assert trade.get(o["public_id"])["status"] == "pending_payment"


def test_a_webhook_alone_cannot_mark_an_order_paid_the_transaction_is_verified(client, trade):
    """A correctly signed webhook for a payment the provider never completed changes nothing."""
    o = trade.order()
    started = client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers).json()
    provider = LocalProvider()
    raw, headers = signed(provider, "charge.success", started["reference"])
    res = client.post(f"{API}/webhooks/local", content=raw, headers=headers)
    assert res.status_code == 200 and res.json()["status"] == "pending"
    assert trade.get(o["public_id"])["status"] == "pending_payment"


def test_webhook_delivered_twice_is_safe(client, trade, db):
    o = trade.order()
    started = client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers).json()
    provider = LocalProvider()
    provider.transactions[started["reference"]]["status"] = "success"
    raw, headers = signed(provider, "charge.success", started["reference"], "evt-42")
    first = client.post(f"{API}/webhooks/local", content=raw, headers=headers).json()
    second = client.post(f"{API}/webhooks/local", content=raw, headers=headers).json()
    assert (first["status"], second["status"]) == ("applied", "duplicate")
    assert trade.get(o["public_id"])["status"] == "paid"
    assert db.query(WebhookEvent).count() == 1
    assert db.query(LedgerEntry).filter_by(kind="payment_received").count() == 3  # one movement of three legs, not two
    assert_ledger_balanced(db)


def test_same_payment_applied_by_webhook_and_by_return_page_only_counts_once(client, trade, db):
    o = trade.order()
    ref, _ = trade.pay(o["public_id"])
    status = client.get(f"{API}/orders/{o['public_id']}/payment-status", params={"reference": ref}, headers=trade.buyer_headers)
    assert status.status_code == 200 and status.json()["status"] == "paid"
    assert db.query(LedgerEntry).filter_by(kind="payment_received").count() == 3
    assert db.query(Payment).count() == 1


def test_amount_mismatch_never_pays_the_order(client, trade, db):
    o = trade.order()
    started = client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers).json()
    LocalProvider.transactions[started["reference"]]["amount"] -= 100  # provider reports a smaller charge
    LocalProvider.transactions[started["reference"]]["status"] = "success"
    raw, headers = signed(LocalProvider(), "charge.success", started["reference"], "evt-short")
    res = client.post(f"{API}/webhooks/local", content=raw, headers=headers).json()
    assert res["status"] == "mismatch"
    assert trade.get(o["public_id"])["status"] == "pending_payment"
    assert db.scalars(select(Payment)).one().status == "failed"


def test_unknown_reference_is_ignored_quietly(client, trade):
    provider = LocalProvider()
    raw, headers = signed(provider, "charge.success", "CPO-NOPE")
    assert client.post(f"{API}/webhooks/local", content=raw, headers=headers).json()["status"] == "ignored"


def test_only_the_buyer_can_pay_or_use_local_checkout(client, trade):
    o = trade.order()
    assert client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.seller_headers).status_code == 403
    assert client.post(f"{API}/orders/{o['public_id']}/pay").status_code == 401
    ref = client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers).json()["reference"]
    assert (
        client.post(
            f"{API}/payments/local/complete", json={"reference": ref, "outcome": "success"}, headers=trade.seller_headers
        ).status_code
        == 404
    )


def test_payment_arriving_after_cancellation_is_refunded(client, trade, db):
    o = trade.order()
    ref = client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers).json()["reference"]
    trade.act(o["public_id"], "cancel", {"reason": "Changed my mind"}, who="buyer")
    LocalProvider.transactions[ref]["status"] = "success"
    raw, headers = signed(LocalProvider(), "charge.success", ref, "late")
    client.post(f"{API}/webhooks/local", content=raw, headers=headers)
    assert trade.get(o["public_id"])["status"] == "cancelled"
    assert db.query(Refund).one().amount_kobo == 10_000 * NAIRA
    assert_ledger_balanced(db)
    assert ledger.balance(db, ledger.ESCROW) == 0


# ---- order stages: only allowed changes, only by the right person --------------------------------------------------------


def test_stage_rules_are_enforced_by_the_backend(trade):
    oid = trade.paid_order()
    assert trade.act(oid, "stage", {"stage": "ready"}, expect=409)  # must accept first
    trade.act(oid, "accept", who="buyer", expect=403)
    trade.act(oid, "accept")
    trade.act(oid, "accept", expect=409)  # already accepted
    trade.act(oid, "stage", {"stage": "delivered"}, expect=409)  # cannot skip preparing/ready
    trade.act(oid, "confirm", who="buyer", expect=409)  # nothing delivered yet
    trade.act(oid, "stage", {"stage": "preparing"})
    trade.act(oid, "stage", {"stage": "ready"})
    trade.act(oid, "stage", {"stage": "preparing"}, expect=409)  # cannot go backwards
    trade.act(oid, "stage", {"stage": "delivered"}, who="buyer", expect=403)
    trade.act(oid, "stage", {"stage": "delivered"})
    trade.act(oid, "cancel", who="buyer", expect=409)  # too late to cancel: report a problem instead
    assert [e["status"] for e in trade.get(oid)["timeline"]] == ["pending_payment", "paid", "accepted", "preparing", "ready", "delivered"]


def test_strangers_cannot_see_or_touch_orders(client, h, trade):
    oid = trade.paid_order()
    h.make_user("stranger@example.com")
    stranger = h.login("stranger@example.com")
    assert client.get(f"{API}/orders/{oid}", headers=stranger).status_code == 404
    for action in ("accept", "confirm", "cancel", "pay"):
        assert client.post(f"{API}/orders/{oid}/{action}", json={}, headers=stranger).status_code == 404
    assert client.get(f"{API}/orders", headers=stranger).json() == []
    assert client.get(f"{API}/orders/{oid}").status_code == 401


# ---- the complete happy path to payout ---------------------------------------------------------------------------------


def test_full_journey_paid_delivered_confirmed_and_paid_out(client, trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    done = trade.act(oid, "confirm", who="buyer")
    assert done["status"] == "confirmed"
    b = balances(db)
    assert b[ledger.ESCROW] == 0
    assert (
        b[ledger.SELLER_PAYABLE] == -8_000 * NAIRA and b[ledger.PLATFORM_REVENUE] == -2_000 * NAIRA
    )  # commission recorded for the platform
    payout = db.scalars(select(Payout)).one()
    assert (payout.status, payout.amount_kobo) == ("pending", 8_000 * NAIRA)
    result = run_due(db)
    assert result["failed"] == 0
    db.refresh(payout)
    assert payout.status == "paid" and payout.paid_at
    assert trade.get(oid)["status"] == "paid_out"
    b = balances(db)
    assert b[ledger.SELLER_PAYABLE] == 0
    assert b[ledger.PROVIDER_CLEARING] + b[ledger.PROVIDER_FEES] == 2_000 * NAIRA  # what is left of the buyer's money is the commission
    assert_ledger_balanced(db)
    shop = db.scalars(select(Shop)).one()
    assert shop.confirmed_deals == 1
    assert "payout.sent" in [n.kind for n in db.scalars(select(Notification))]
    # running the cron again must not pay twice
    run_due(db, now=utcnow() + timedelta(hours=1))
    assert db.query(Payout).filter_by(status="paid").count() == 1
    assert db.query(LedgerEntry).filter_by(kind="payout").count() == 2


def test_seller_earnings_summary(client, trade, db):
    paid_out = trade.paid_order()
    trade.to_delivered(paid_out)
    trade.act(paid_out, "confirm", who="buyer")
    run_due(db)
    held = trade.paid_order()
    e = client.get(f"{API}/seller/earnings", headers=trade.seller_headers).json()
    assert (e["gross_sales_kobo"], e["commission_kobo"], e["net_earnings_kobo"]) == (10_000 * NAIRA, 2_000 * NAIRA, 8_000 * NAIRA)
    assert (e["held_kobo"], e["paid_payouts_kobo"], e["processing_payouts_kobo"]) == (8_000 * NAIRA, 8_000 * NAIRA, 0)
    assert e["payouts"][0]["order"] == paid_out and held
    assert client.get(f"{API}/seller/earnings", headers=trade.buyer_headers).status_code == 403


def test_seller_order_list_hides_unpaid_orders(client, trade):
    trade.order()
    assert client.get(f"{API}/seller/orders", headers=trade.seller_headers).json() == []
    oid = trade.paid_order()
    assert [o["public_id"] for o in client.get(f"{API}/seller/orders", headers=trade.seller_headers).json()] == [oid]
    assert len(client.get(f"{API}/orders", headers=trade.buyer_headers).json()) == 2


def test_payout_is_held_until_payout_details_exist(client, h, db):
    t = Trade(client, h, db, payout=False)
    oid = t.paid_order()
    t.to_delivered(oid)
    t.act(oid, "confirm", who="buyer")
    payout = db.scalars(select(Payout)).one()
    assert payout.status == "held" and "details" in payout.hold_reason
    boss = admin(client, h)
    assert (
        client.post(
            f"{API}/admin/payouts/{payout.id}/action", json={"action": "release", "reason": "Details added"}, headers=boss
        ).status_code
        == 409
    )
    client.patch(
        f"{API}/seller/settings",
        json={"payout_bank": "GTBank", "payout_account_number": "0123456789", "payout_account_name": "Trade Shop"},
        headers=t.seller_headers,
    )
    released = client.post(f"{API}/admin/payouts/{payout.id}/action", json={"action": "release", "reason": "Details added"}, headers=boss)
    assert released.status_code == 200 and released.json()["status"] == "pending"
    run_due(db)
    assert db.get(Payout, payout.id).status == "paid"


# ---- cancellations and refunds --------------------------------------------------------------------------------------------


def test_buyer_cancels_before_paying_nothing_to_refund(trade, db):
    o = trade.order()
    cancelled = trade.act(o["public_id"], "cancel", {"reason": "Not needed"}, who="buyer")
    assert cancelled["status"] == "cancelled" and db.query(Refund).count() == 0


def test_buyer_cancels_before_acceptance_gets_full_refund_and_stock_returns(trade, db):
    oid = trade.paid_order(quantity=2)
    assert db.get(Listing, 1).quantity == 3
    trade.act(oid, "cancel", {"reason": "Found it elsewhere"}, who="buyer")
    assert trade.get(oid)["status"] == "cancelled"
    refund = db.scalars(select(Refund)).one()
    assert (refund.amount_kobo, refund.status) == (20_000 * NAIRA, "done")
    assert db.get(Listing, 1).quantity == 5
    assert ledger.balance(db, ledger.ESCROW) == 0 and ledger.balance(db, ledger.PLATFORM_REVENUE) == 0
    assert_ledger_balanced(db)
    assert db.query(Payout).count() == 0


def test_seller_declining_refunds_the_buyer_in_full_including_commission(trade, db):
    oid = trade.paid_order(fulfilment="delivery")
    trade.act(oid, "decline", {"reason": "Out of stock"})
    assert trade.get(oid)["status"] == "cancelled"
    assert db.scalars(select(Refund)).one().amount_kobo == 10_500 * NAIRA
    assert balances(db)[ledger.PLATFORM_REVENUE] == 0
    assert_ledger_balanced(db)
    trade.act(oid, "decline", expect=409)


def test_seller_cancelling_after_accepting_also_refunds(trade, db):
    oid = trade.paid_order()
    trade.act(oid, "accept")
    trade.act(oid, "cancel", {"reason": "Cannot make it"})
    assert trade.get(oid)["status"] == "cancelled"
    assert db.scalars(select(Refund)).one().amount_kobo == 10_000 * NAIRA


def test_seller_does_not_accept_in_time_so_order_cancels_and_refunds(trade, db):
    oid = trade.paid_order()
    run_due(db)
    assert trade.get(oid)["status"] == "paid"  # still inside the window
    order = db.scalars(select(Order)).one()
    order.accept_by = utcnow() - timedelta(minutes=1)
    db.commit()
    run_due(db, now=utcnow() + timedelta(hours=1))
    cancelled = trade.get(oid)
    assert cancelled["status"] == "cancelled" and "did not accept" in cancelled["cancel_reason"]
    assert db.scalars(select(Refund)).one().amount_kobo == 10_000 * NAIRA
    assert_ledger_balanced(db)
    kinds = [n.kind for n in db.scalars(select(Notification))]
    assert kinds.count("order.cancelled") >= 2  # buyer and seller both told


def test_accept_window_is_an_admin_setting(client, h, trade, db):
    boss = admin(client, h)
    client.put(f"{API}/admin/settings/seller_accept_hours", json={"value": 6, "reason": "Exam week"}, headers=boss)
    oid = trade.paid_order()
    order = db.scalars(select(Order).where(Order.public_id == oid)).one()
    assert timedelta(hours=5, minutes=55) < order.accept_by - order.paid_at <= timedelta(hours=6, minutes=1)


def test_unpaid_orders_expire(trade, db):
    o = trade.order()
    order = db.scalars(select(Order)).one()
    order.created_at = utcnow() - timedelta(hours=25)
    db.commit()
    run_due(db)
    assert trade.get(o["public_id"])["status"] == "cancelled"


def test_auto_confirmation_after_the_window_pays_the_seller(trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    order = db.scalars(select(Order)).one()
    assert timedelta(hours=47) < order.auto_confirm_at - order.delivered_at <= timedelta(hours=48, minutes=1)
    run_due(db)
    assert trade.get(oid)["status"] == "delivered"
    order.auto_confirm_at = utcnow() - timedelta(minutes=1)
    db.commit()
    run_due(db, now=utcnow() + timedelta(hours=1))
    run_due(db, now=utcnow() + timedelta(hours=2))
    assert trade.get(oid)["status"] == "paid_out"
    assert_ledger_balanced(db)


def test_reminders_are_sent_once(trade, db):
    oid = trade.paid_order()
    order = db.scalars(select(Order)).one()
    order.accept_by = utcnow() + timedelta(minutes=20)
    db.commit()
    run_due(db)
    run_due(db, now=utcnow() + timedelta(minutes=1))
    assert [n.kind for n in db.scalars(select(Notification))].count("order.reminder") == 1
    assert oid


# ---- disputes -------------------------------------------------------------------------------------------------------------


def open_problem(trade, oid, reason="not_as_described", details="It is not what the photos showed"):
    res = trade.client.post(f"{API}/orders/{oid}/problem", json={"reason": reason, "details": details}, headers=trade.buyer_headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_buyer_reports_problem_payout_pauses_and_seller_responds(client, trade, db, tmp_path, monkeypatch):
    from app.adapters import storage

    monkeypatch.setattr("app.features.orders.router.get_storage", lambda: storage.LocalStorage(tmp_path))
    oid = trade.paid_order()
    trade.to_delivered(oid)
    out = open_problem(trade, oid)
    assert out["status"] == "disputed" and out["dispute"]["public_id"].startswith("CP-D-")
    assert db.scalars(select(Order)).one().auto_confirm_at is None
    run_due(db, now=utcnow() + timedelta(days=5))
    assert trade.get(oid)["status"] == "disputed" and db.query(Payout).count() == 0  # nothing is paid while disputed
    assert client.post(f"{API}/orders/{oid}/problem", json={"reason": "other"}, headers=trade.buyer_headers).status_code == 409
    did = out["dispute"]["public_id"]
    assert client.post(f"{API}/disputes/{did}/respond", json={"message": "It matches"}, headers=trade.buyer_headers).status_code == 403
    responded = client.post(
        f"{API}/disputes/{did}/respond", json={"message": "The item matches the listing photos exactly."}, headers=trade.seller_headers
    ).json()
    assert responded["dispute"]["status"] == "under_review"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    ev = client.post(
        f"{API}/disputes/{did}/evidence",
        data={"note": "My photo before handover"},
        files={"file": ("p.png", png, "image/png")},
        headers=trade.seller_headers,
    )
    assert ev.status_code == 200
    img = [e for e in ev.json()["dispute"]["evidence"] if e["image"]][0]["image"]
    assert client.get(img).status_code == 200
    assert client.get(img.rsplit("/", 1)[0] + "/not-a-token").status_code == 404
    assert client.post(f"{API}/disputes/{did}/evidence", data={"note": "x"}).status_code == 401


def test_admin_full_refund_returns_everything_including_commission(client, h, trade, db):
    oid = trade.paid_order(fulfilment="delivery")
    trade.to_delivered(oid)
    did = open_problem(trade, oid)["dispute"]["public_id"]
    boss = admin(client, h)
    res = client.post(
        f"{API}/admin/disputes/{did}/decide", json={"decision": "full_refund", "reason": "Item not as described"}, headers=boss
    )
    assert res.status_code == 200 and res.json()["order"]["status"] == "refunded"
    assert db.scalars(select(Refund)).one().amount_kobo == 10_500 * NAIRA
    b = balances(db)
    assert b[ledger.ESCROW] == 0 and b[ledger.PLATFORM_REVENUE] == 0 and b[ledger.SELLER_PAYABLE] == 0
    assert_ledger_balanced(db)
    assert db.query(Payout).count() == 0
    assert db.scalars(select(Dispute)).one().resolution == "full_refund"
    kinds = [(n.kind, n.user_id) for n in db.scalars(select(Notification)) if n.kind == "dispute.resolved"]
    assert len(kinds) == 2  # both people are told the result
    assert (
        client.post(f"{API}/admin/disputes/{did}/decide", json={"decision": "release", "reason": "again"}, headers=boss).status_code == 409
    )


def test_admin_partial_refund_reduces_commission_proportionally(client, h, trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    did = open_problem(trade, oid)["dispute"]["public_id"]
    boss = admin(client, h)
    assert (
        client.post(
            f"{API}/admin/disputes/{did}/decide", json={"decision": "partial_refund", "refund_item_kobo": 0, "reason": "bad"}, headers=boss
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API}/admin/disputes/{did}/decide",
            json={"decision": "partial_refund", "refund_item_kobo": 10_000 * NAIRA, "reason": "bad"},
            headers=boss,
        ).status_code
        == 422
    )
    res = client.post(
        f"{API}/admin/disputes/{did}/decide",
        json={"decision": "partial_refund", "refund_item_kobo": 2_500 * NAIRA, "reason": "Minor damage"},
        headers=boss,
    )
    assert res.status_code == 200
    seller = trade.get(oid, "seller")
    assert seller["commission_kobo"] == 1_500 * NAIRA  # 2,000 less 500 returned (25% of it)
    assert seller["seller_amount_kobo"] == 6_000 * NAIRA  # 10,000 - 2,500 refunded - 1,500 commission
    assert db.scalars(select(Refund)).one().amount_kobo == 2_500 * NAIRA
    b = balances(db)
    assert b[ledger.SELLER_PAYABLE] == -6_000 * NAIRA and b[ledger.PLATFORM_REVENUE] == -1_500 * NAIRA and b[ledger.ESCROW] == 0
    assert_ledger_balanced(db)
    run_due(db)
    assert db.scalars(select(Payout)).one().amount_kobo == 6_000 * NAIRA
    assert trade.get(oid)["status"] == "paid_out"
    assert db.scalars(select(Shop)).one().confirmed_deals == 0  # a partly refunded deal does not count towards trust


def test_admin_release_pays_the_seller_in_full(client, h, trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    did = open_problem(trade, oid, "not_received")["dispute"]["public_id"]
    boss = admin(client, h)
    client.post(f"{API}/admin/disputes/{did}/decide", json={"decision": "release", "reason": "Courier confirmed delivery"}, headers=boss)
    run_due(db)
    assert trade.get(oid)["status"] == "paid_out"
    assert db.scalars(select(Payout)).one().amount_kobo == 8_000 * NAIRA
    assert balances(db)[ledger.PLATFORM_REVENUE] == -2_000 * NAIRA
    assert_ledger_balanced(db)


def test_only_admins_who_are_not_involved_can_decide_disputes(client, h, trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    did = open_problem(trade, oid)["dispute"]["public_id"]
    body = {"decision": "release", "reason": "Trying my luck"}
    assert client.post(f"{API}/admin/disputes/{did}/decide", json=body, headers=trade.seller_headers).status_code == 403
    assert client.post(f"{API}/admin/disputes/{did}/decide", json=body, headers=trade.buyer_headers).status_code == 403
    assert client.post(f"{API}/admin/disputes/{did}/decide", json=body).status_code == 401
    buyer = db.scalars(select(User).where(User.email == "buyer@example.com")).one()
    buyer.role = "admin"
    db.commit()
    involved = h.login("buyer@example.com")
    assert client.post(f"{API}/admin/disputes/{did}/decide", json=body, headers=involved).status_code == 403


def test_seller_silence_sends_the_dispute_to_an_admin(client, h, trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    open_problem(trade, oid)
    dispute = db.scalars(select(Dispute)).one()
    assert dispute.status == "awaiting_seller"
    assert timedelta(hours=47) < dispute.response_due_at - utcnow() <= timedelta(hours=48)
    dispute.response_due_at = utcnow() - timedelta(minutes=1)
    db.commit()
    boss = admin(client, h)
    run_due(db, now=utcnow() + timedelta(minutes=1))
    db.refresh(dispute)
    assert dispute.status == "under_review"
    listed = client.get(f"{API}/admin/disputes", params={"status": "under_review"}, headers=boss).json()
    assert [d["public_id"] for d in listed] == [dispute.public_id]


def test_disputed_chat_becomes_visible_to_admins_with_a_logged_reason(client, h, trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    client.post(f"{API}/conversations/{trade.convo}/messages", json={"body": "Where is it?"}, headers=trade.buyer_headers)
    boss = admin(client, h)
    assert client.get(f"{API}/admin/conversations/{trade.convo}", params={"reason": "Checking context"}, headers=boss).status_code == 403
    open_problem(trade, oid)
    assert (
        client.get(f"{API}/admin/conversations/{trade.convo}", params={"reason": "Checking dispute context"}, headers=boss).status_code
        == 200
    )


def test_no_show_for_services(client, h, db):
    t = Trade(client, h, db, type="service", category_id=category_id(db, "services"), condition=None, quantity=1)
    soon = (utcnow() + timedelta(days=3)).isoformat()
    assert (
        client.post(f"{API}/orders", json={"listing_id": t.listing["public_id"]}, headers=t.buyer_headers).status_code == 422
    )  # booking time needed
    assert (
        client.post(
            f"{API}/orders",
            json={"listing_id": t.listing["public_id"], "booking_at": (utcnow() - timedelta(days=1)).isoformat()},
            headers=t.buyer_headers,
        ).status_code
        == 422
    )
    oid = client.post(f"{API}/orders", json={"listing_id": t.listing["public_id"], "booking_at": soon}, headers=t.buyer_headers).json()[
        "public_id"
    ]
    t.pay(oid)
    t.act(oid, "accept")
    buyer_view = t.get(oid)
    assert "cancel" in buyer_view["actions"]  # more than 24 hours before the booking
    t.act(oid, "no-show", expect=409)  # booking time has not passed
    order = db.scalars(select(Order)).one()
    order.booking_at = utcnow() - timedelta(hours=1)
    db.commit()
    assert "cancel" not in t.get(oid)["actions"] and "buyer_no_show" in t.get(oid, "seller")["actions"]
    res = t.act(oid, "no-show")
    assert res["status"] == "disputed" and res["dispute"]["reason"] == "no_show"


def test_service_deposit_is_all_that_is_charged_in_app(client, h, db):
    t = Trade(
        client, h, db, type="service", category_id=category_id(db, "services"), condition=None, quantity=1, deposit_kobo=2_000 * NAIRA
    )
    o = client.post(
        f"{API}/orders",
        json={"listing_id": t.listing["public_id"], "booking_at": (utcnow() + timedelta(days=2)).isoformat()},
        headers=t.buyer_headers,
    ).json()
    assert (o["deposit_only"], o["item_paid_kobo"], o["buyer_total_kobo"]) == (True, 2_000 * NAIRA, 2_000 * NAIRA)
    oid = o["public_id"]
    t.pay(oid)
    assert t.get(oid, "seller")["commission_kobo"] == 400 * NAIRA


# ---- other deal types and settings --------------------------------------------------------------------------------------


def test_offline_deal_needs_both_people_and_is_not_protected(client, trade, db):
    res = client.post(
        f"{API}/orders/offline", json={"conversation_id": trade.convo, "agreed_price_kobo": 9_000 * NAIRA}, headers=trade.buyer_headers
    )
    assert res.status_code == 201
    o = res.json()
    assert (o["protected"], o["payment_method"], o["status"], o["commission_kobo"]) == (False, "offline", "accepted", None)
    assert client.post(f"{API}/orders/{o['public_id']}/problem", json={"reason": "other"}, headers=trade.buyer_headers).status_code == 409
    assert client.post(f"{API}/orders/{o['public_id']}/pay", headers=trade.buyer_headers).status_code == 409
    assert client.post(f"{API}/orders/{o['public_id']}/confirm", headers=trade.buyer_headers).status_code == 409
    done = client.post(f"{API}/orders/{o['public_id']}/confirm-offline", headers=trade.seller_headers).json()
    assert done["status"] == "confirmed"
    assert db.query(LedgerEntry).count() == 0 and db.query(Payout).count() == 0  # no money moves through the app
    assert db.scalars(select(Shop)).one().confirmed_deals == 1
    other = client.post(f"{API}/orders/offline", json={"conversation_id": 999, "agreed_price_kobo": 100}, headers=trade.buyer_headers)
    assert other.status_code == 404


def test_instant_split_fallback_pays_the_seller_at_payment_time(client, h, trade, db):
    boss = admin(client, h)
    client.put(f"{API}/admin/settings/instant_split", json={"value": True, "reason": "Provider cannot hold funds"}, headers=boss)
    oid = trade.paid_order()
    assert trade.get(oid)["status"] == "confirmed"
    assert db.scalars(select(Payout)).one().status == "pending"
    run_due(db)
    assert trade.get(oid)["status"] == "paid_out"
    b = balances(db)
    assert b[ledger.ESCROW] == 0 and b[ledger.SELLER_PAYABLE] == 0 and b[ledger.PLATFORM_REVENUE] == -2_000 * NAIRA
    assert_ledger_balanced(db)


def test_provider_fee_is_absorbed_by_the_platform_by_default_and_can_move_to_the_seller(client, h, trade, db):
    oid = trade.paid_order()
    order = db.scalars(select(Order)).one()
    fee = order.provider_fee_kobo
    assert fee > 0 and trade.get(oid, "seller")["seller_amount_kobo"] == 8_000 * NAIRA
    boss = admin(client, h)
    client.put(f"{API}/admin/settings/provider_fee_absorbed", json={"value": False, "reason": "Margins"}, headers=boss)
    oid2 = trade.paid_order()
    order2 = db.scalars(select(Order).where(Order.public_id == oid2)).one()
    assert order2.provider_fee_absorbed is False
    assert trade.get(oid2, "seller")["seller_amount_kobo"] == 8_000 * NAIRA - order2.provider_fee_kobo
    trade.to_delivered(oid2)
    trade.act(oid2, "confirm", who="buyer")
    assert_ledger_balanced(db)


# ---- admin views ------------------------------------------------------------------------------------------------------------


def test_admin_can_search_orders_by_id_and_see_money_details(client, h, trade, db):
    oid = trade.paid_order()
    boss = admin(client, h)
    found = client.get(f"{API}/admin/orders", params={"q": oid}, headers=boss).json()
    assert [r["public_id"] for r in found] == [oid]
    detail = client.get(f"{API}/admin/orders/{oid}", headers=boss).json()
    assert detail["role"] == "admin" and detail["commission_kobo"] == 2_000 * NAIRA
    assert client.get(f"{API}/admin/orders/{oid}", headers=trade.buyer_headers).status_code == 403
    pays = client.get(f"{API}/admin/payments", headers=boss).json()
    assert pays[0]["order_id"] == oid and pays[0]["status"] == "success"
    rev = client.get(f"{API}/admin/revenue", headers=boss).json()
    assert (rev["gmv_kobo"], rev["held_in_escrow_kobo"], rev["orders_paid"]) == (10_000 * NAIRA, 10_000 * NAIRA, 1)
    com = client.get(f"{API}/admin/commission", headers=boss).json()
    assert com["default_bps"] == 2000
    assert client.get(f"{API}/admin/ledger", headers=boss).json()


def test_admin_can_hold_a_pending_payout(client, h, trade, db):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    trade.act(oid, "confirm", who="buyer")
    payout = db.scalars(select(Payout)).one()
    boss = admin(client, h)
    assert (
        client.post(f"{API}/admin/payouts/{payout.id}/action", json={"action": "hold", "reason": "Investigating"}, headers=boss).json()[
            "status"
        ]
        == "held"
    )
    run_due(db)
    assert db.get(Payout, payout.id).status == "held"
    assert (
        client.post(f"{API}/admin/payouts/{payout.id}/action", json={"action": "release", "reason": "ok"}, headers=boss).status_code == 422
    )


def test_account_deletion_is_blocked_while_orders_or_disputes_are_open(client, h, trade, db):
    oid = trade.paid_order()
    for headers in (trade.buyer_headers, trade.seller_headers):
        res = client.delete(f"{API}/me", headers=headers)
        assert res.status_code == 409 and "open order" in res.json()["detail"]
    trade.to_delivered(oid)
    trade.act(oid, "confirm", who="buyer")
    run_due(db)
    assert client.delete(f"{API}/me", headers=trade.buyer_headers).status_code == 204


def test_ledger_rejects_unbalanced_movements(db):
    with pytest.raises(ValueError):
        ledger.post(db, order=None, kind="oops", legs=[(ledger.ESCROW, 100), (ledger.SELLER_PAYABLE, -99)])


def test_setting_change_does_not_touch_existing_orders(client, h, trade, db):
    oid = trade.paid_order()
    boss = admin(client, h)
    for key, value in (("commission_bps", 500), ("buyer_confirm_hours", 1)):
        client.put(f"{API}/admin/settings/{key}", json={"value": value, "reason": "Change for new orders"}, headers=boss)
    seller = trade.get(oid, "seller")
    assert seller["commission_bps"] == 2000 and seller["commission_kobo"] == 2_000 * NAIRA
    assert db.get(Setting, "commission_bps").value == 500
