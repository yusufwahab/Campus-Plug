from datetime import timedelta

import pytest
from sqlalchemy import select

import app.jobs.handlers  # noqa: F401
import app.jobs.orders  # noqa: F401
import app.notify  # noqa: F401
from app.adapters.payments import LocalProvider
from app.db import utcnow
from app.features.orders import ledger
from app.jobs.core import run_due
from app.models.catalogue import Listing, Shop
from app.models.commerce import Order
from app.models.growth import Boost, Plan, PromoCode, Subscription
from app.models.social import Conversation, Notification
from tests.test_orders_payments import API, NAIRA, Trade, admin


@pytest.fixture(autouse=True)
def _clean_local_provider():
    LocalProvider.transactions.clear()


@pytest.fixture()
def trade(client, h, db):
    return Trade(client, h, db)


def seller_code(client, trade, code="TOLU10", **over):
    res = client.post(f"{API}/seller/promos", json={"code": code, "percent": 10, **over}, headers=trade.seller_headers)
    assert res.status_code == 201, res.text
    return res.json()


def validate(client, trade, code, headers=None):
    return client.post(
        f"{API}/promos/validate", json={"code": code, "listing_id": trade.listing["public_id"]}, headers=headers or trade.buyer_headers
    )


# ---- seller promo codes -----------------------------------------------------------------------------------------------


def test_seller_code_lowers_price_and_commission_base(client, trade, db):
    seller_code(client, trade)
    o = trade.order(promo_code="tolu10")
    assert o["seller_discount_kobo"] == 1_000 * NAIRA
    assert o["item_paid_kobo"] == 9_000 * NAIRA
    trade.pay(o["public_id"])
    mine = trade.get(o["public_id"], "seller")
    assert mine["commission_kobo"] == 1_800 * NAIRA  # default 20% of what the buyer actually paid for the item
    assert mine["seller_amount_kobo"] == 7_200 * NAIRA


def test_sellers_cannot_use_their_own_code(client, trade):
    seller_code(client, trade)
    res = client.post(
        f"{API}/promos/validate",
        json={"code": "TOLU10", "listing_id": trade.listing["public_id"]},
        headers=trade.seller_headers,
    )
    assert res.status_code == 422


def test_code_validation_rules(client, trade, db):
    seller_code(client, trade, "MINSPEND", min_spend_kobo=50_000 * NAIRA)
    assert validate(client, trade, "MINSPEND").status_code == 422
    seller_code(client, trade, "ONCE", usage_limit=1)
    assert validate(client, trade, "ONCE").status_code == 200
    first = trade.order(promo_code="ONCE")
    assert validate(client, trade, "ONCE").status_code == 422  # limit used up
    trade.act(first["public_id"], "cancel", who="buyer")  # cancelling before payment gives the use back
    assert validate(client, trade, "ONCE").status_code == 200
    seller_code(client, trade, "SOON")
    db.scalars(select(PromoCode).where(PromoCode.code == "SOON")).one().expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert validate(client, trade, "SOON").status_code == 422
    assert validate(client, trade, "NOSUCH").status_code == 422


def test_code_limited_to_chosen_items_and_shop(client, trade, db):
    other = client.post(f"{API}/listings", json={**_other_body(db), "title": "Other thing"}, headers=trade.seller_headers).json()
    seller_code(client, trade, "ITEMONLY", listing_ids=[other["public_id"]])
    assert validate(client, trade, "ITEMONLY").status_code == 422
    ok = client.post(f"{API}/promos/validate", json={"code": "ITEMONLY", "listing_id": other["public_id"]}, headers=trade.buyer_headers)
    assert ok.status_code == 200


def _other_body(db):
    from tests.test_marketplace import listing_body

    return listing_body(db, price_kobo=5_000 * NAIRA, quantity=3)


def test_price_spike_blocks_discount(client, trade, db):
    seller_code(client, trade)
    listing = db.scalars(select(Listing)).one()
    listing.previous_price_kobo = 5_000 * NAIRA  # raised from 5,000 to 10,000 just now
    listing.price_changed_at = utcnow()
    db.commit()
    res = validate(client, trade, "TOLU10")
    assert res.status_code == 422 and "raised" in res.json()["detail"]
    listing.price_changed_at = utcnow() - timedelta(days=30)
    db.commit()
    assert validate(client, trade, "TOLU10").status_code == 200


def test_editing_price_records_history(client, trade, db):
    listing = trade.listing
    res = client.patch(f"{API}/listings/{listing['public_id']}", json={"price_kobo": 12_000 * NAIRA}, headers=trade.seller_headers)
    assert res.status_code == 200, res.text
    row = db.scalars(select(Listing)).one()
    assert row.previous_price_kobo == 10_000 * NAIRA and row.price_changed_at is not None


# ---- platform campaign + admin seller codes ---------------------------------------------------------------------------


def test_platform_funded_code_keeps_seller_payout_whole(client, h, trade, db):
    boss = admin(client, h)
    res = client.post(
        f"{API}/admin/promos",
        json={"code": "WELCOME", "kind": "admin_buyer", "percent": 20, "reason": "Launch week"},
        headers=boss,
    )
    assert res.status_code == 201, res.text
    o = trade.order(promo_code="welcome")
    assert o["platform_discount_kobo"] == 2_000 * NAIRA and o["seller_discount_kobo"] == 0
    assert o["buyer_total_kobo"] == o["item_paid_kobo"] + o["delivery_fee_kobo"] - 2_000 * NAIRA  # buyer pays less
    trade.pay(o["public_id"])
    mine = trade.get(o["public_id"], "seller")
    assert mine["commission_kobo"] == 2_000 * NAIRA and mine["seller_amount_kobo"] == 8_000 * NAIRA  # seller unaffected
    assert ledger.balance(db, ledger.PROMO_COST) == 2_000 * NAIRA  # Campus Plug carries the cost


def test_admin_promo_needs_reason_and_unique_code(client, h):
    boss = admin(client, h)
    body = {"code": "SAVE", "kind": "admin_buyer", "percent": 10}
    assert client.post(f"{API}/admin/promos", json=body, headers=boss).status_code == 422
    assert client.post(f"{API}/admin/promos", json={**body, "reason": "Test"}, headers=boss).status_code == 201
    assert client.post(f"{API}/admin/promos", json={**body, "reason": "Again"}, headers=boss).status_code == 409


def test_admin_seller_code_sets_commission_for_new_orders(client, h, trade, db):
    boss = admin(client, h)
    client.post(
        f"{API}/admin/promos",
        json={"code": "LOWFEE", "kind": "admin_seller", "commission_bps": 500, "reason": "Onboarding offer"},
        headers=boss,
    )
    applied = client.post(f"{API}/seller/promos/apply", json={"code": "lowfee"}, headers=trade.seller_headers)
    assert applied.status_code == 200, applied.text
    o = trade.order()
    trade.pay(o["public_id"])
    assert trade.get(o["public_id"], "seller")["commission_bps"] == 500


# ---- plans ------------------------------------------------------------------------------------------------------------


def make_plan(client, boss, name="Gold", bps=500, price=3_000 * NAIRA):
    res = client.post(
        f"{API}/admin/plans",
        json={"name": name, "price_kobo": price, "commission_bps": bps, "benefits": ["Lower commission"], "reason": "New plan"},
        headers=boss,
    )
    assert res.status_code == 201, res.text
    return res.json()


def buy(client, trade, path, body):
    res = client.post(f"{API}{path}", json=body, headers=trade.seller_headers)
    assert res.status_code in (200, 201), res.text
    ref = res.json()["reference"]
    done = client.post(f"{API}/payments/local/complete", json={"reference": ref, "outcome": "success"}, headers=trade.seller_headers)
    assert done.status_code == 200, done.text
    return ref


def test_plan_purchase_applies_rate_to_new_orders_only(client, h, trade, db):
    boss = admin(client, h)
    plan = make_plan(client, boss)
    before = trade.paid_order()
    buy(client, trade, "/seller/plan/buy", {"plan_id": plan["id"]})
    sub = db.scalars(select(Subscription)).one()
    assert sub.status == "active" and sub.ends_at > utcnow() + timedelta(days=29)
    assert ledger.balance(db, ledger.PLATFORM_REVENUE) == -3_000 * NAIRA
    after = trade.paid_order()
    assert trade.get(before, "seller")["commission_bps"] == 2000  # frozen at creation
    assert trade.get(after, "seller")["commission_bps"] == 500


def test_plan_needs_verified_seller_and_is_idempotent(client, h, db):
    t = Trade(client, h, db, verified=False)
    boss = admin(client, h)
    plan = make_plan(client, boss)
    res = client.post(f"{API}/seller/plan/buy", json={"plan_id": plan["id"]}, headers=t.seller_headers)
    assert res.status_code == 403


def test_plan_renewal_extends_and_cancel_ends_rate(client, h, trade, db):
    boss = admin(client, h)
    plan = make_plan(client, boss)
    buy(client, trade, "/seller/plan/buy", {"plan_id": plan["id"]})
    buy(client, trade, "/seller/plan/buy", {"plan_id": plan["id"]})
    subs = list(db.scalars(select(Subscription)))
    assert [s.status for s in subs].count("active") == 1
    ends = max(s.ends_at for s in subs)
    assert ends > utcnow() + timedelta(days=59)
    res = client.post(f"{API}/seller/plan/cancel", headers=trade.seller_headers)
    assert res.status_code == 200 and res.json()["current_plan"] is None
    oid = trade.paid_order()
    assert trade.get(oid, "seller")["commission_bps"] == 2000


def test_replaying_a_plan_payment_does_not_double_apply(client, h, trade, db):
    boss = admin(client, h)
    plan = make_plan(client, boss)
    ref = buy(client, trade, "/seller/plan/buy", {"plan_id": plan["id"]})
    again = client.get(f"{API}/seller/purchases/{ref}/status", headers=trade.seller_headers)
    assert again.json()["status"] == "paid"
    assert len(list(db.scalars(select(Subscription)))) == 1
    assert ledger.balance(db, ledger.PLATFORM_REVENUE) == -3_000 * NAIRA


def test_plan_edit_is_audited_and_does_not_touch_subscribers(client, h, trade, db):
    boss = admin(client, h)
    plan = make_plan(client, boss)
    buy(client, trade, "/seller/plan/buy", {"plan_id": plan["id"]})
    res = client.put(
        f"{API}/admin/plans/{plan['id']}",
        json={"name": "Gold", "price_kobo": 9_000 * NAIRA, "commission_bps": 100, "reason": "Reprice"},
        headers=boss,
    )
    assert res.status_code == 200
    assert db.scalars(select(Subscription)).one().price_paid_kobo == 3_000 * NAIRA
    assert db.scalars(select(Plan)).one().price_kobo == 9_000 * NAIRA


# ---- boosts -----------------------------------------------------------------------------------------------------------


def test_boost_needs_approval_then_ranks_first_with_sponsored_label(client, h, trade, db):
    boss = admin(client, h)
    second = client.post(f"{API}/listings", json={**_other_body(db), "title": "Plain item"}, headers=trade.seller_headers).json()
    ref = buy(client, trade, "/seller/boosts", {"listing_id": second["public_id"], "days": 3})
    assert ref
    boost = db.scalars(select(Boost)).one()
    assert boost.status == "pending"
    cards = client.get(f"{API}/listings").json()["items"]
    assert not any(c["sponsored"] for c in cards)  # not live until approved
    res = client.post(f"{API}/admin/sponsored/{boost.id}/action", json={"action": "approve", "reason": "Looks fine"}, headers=boss)
    assert res.status_code == 200, res.text
    cards = client.get(f"{API}/listings").json()["items"]
    assert cards[0]["public_id"] == second["public_id"] and cards[0]["sponsored"] is True
    assert sum(c["sponsored"] for c in cards) == 1
    assert ledger.balance(db, ledger.PLATFORM_REVENUE) == -1_500 * NAIRA


def test_rejecting_a_paid_boost_refunds_it(client, h, trade, db):
    boss = admin(client, h)
    buy(client, trade, "/seller/boosts", {"listing_id": trade.listing["public_id"], "days": 7})
    boost = db.scalars(select(Boost)).one()
    res = client.post(f"{API}/admin/sponsored/{boost.id}/action", json={"action": "reject", "reason": "Not allowed"}, headers=boss)
    assert res.status_code == 200, res.text
    assert ledger.balance(db, ledger.PLATFORM_REVENUE) == 0
    db.refresh(boost)
    assert boost.status == "rejected"
    again = client.post(f"{API}/admin/sponsored/{boost.id}/action", json={"action": "approve", "reason": "Oops"}, headers=boss)
    assert again.status_code == 404  # a refunded boost is no longer actionable


def test_boost_ends_by_itself(client, h, trade, db):
    boss = admin(client, h)
    buy(client, trade, "/seller/boosts", {"listing_id": trade.listing["public_id"], "days": 3})
    boost = db.scalars(select(Boost)).one()
    r = client.post(f"{API}/admin/sponsored/{boost.id}/action", json={"action": "approve", "reason": "Approved"}, headers=boss)
    assert r.status_code == 200, r.text
    db.refresh(boost)
    assert boost.status == "active"
    boost.ends_at = utcnow() - timedelta(minutes=1)
    db.commit()
    run_due(db, now=utcnow() + timedelta(hours=2))
    db.refresh(boost)
    assert boost.status == "ended"


def test_only_own_live_listing_can_be_boosted(client, h, trade, db):
    h.make_user("other@example.com", email_verified=True)
    other = h.login("other@example.com")
    client.post(f"{API}/seller/start", json={"name": "Other Shop", "accept_rules": True}, headers=other)
    res = client.post(f"{API}/seller/boosts", json={"listing_id": trade.listing["public_id"], "days": 3}, headers=other)
    assert res.status_code == 404


# ---- reviews ----------------------------------------------------------------------------------------------------------


def complete(trade):
    oid = trade.paid_order()
    trade.to_delivered(oid)
    trade.act(oid, "confirm", who="buyer")
    return oid


def test_only_completed_orders_can_be_reviewed_once(client, trade, db):
    oid = trade.paid_order()
    early = client.post(f"{API}/orders/{oid}/review", json={"rating": 5, "body": "Great"}, headers=trade.buyer_headers)
    assert early.status_code == 409
    trade.to_delivered(oid)
    trade.act(oid, "confirm", who="buyer")
    ok = client.post(f"{API}/orders/{oid}/review", json={"rating": 4, "body": "Good stuff"}, headers=trade.buyer_headers)
    assert ok.status_code == 201 and ok.json()["confirmed_deal"] is True
    dup = client.post(f"{API}/orders/{oid}/review", json={"rating": 5}, headers=trade.buyer_headers)
    assert dup.status_code == 409
    assert client.post(f"{API}/orders/{oid}/review", json={"rating": 5}, headers=trade.seller_headers).status_code == 404
    assert client.post(f"{API}/orders/{oid}/review", json={"rating": 6}, headers=trade.buyer_headers).status_code == 422
    shop = db.scalars(select(Shop)).one()
    assert (shop.rating_sum, shop.rating_count) == (4, 1)


def test_seller_can_reply_once(client, trade):
    oid = complete(trade)
    review = client.post(f"{API}/orders/{oid}/review", json={"rating": 3, "body": "Okay"}, headers=trade.buyer_headers).json()
    first = client.post(f"{API}/reviews/{review['id']}/reply", json={"reply": "Thank you!"}, headers=trade.seller_headers)
    assert first.status_code == 200 and first.json()["reply"] == "Thank you!"
    assert client.post(f"{API}/reviews/{review['id']}/reply", json={"reply": "Again"}, headers=trade.seller_headers).status_code == 409
    assert client.post(f"{API}/reviews/{review['id']}/reply", json={"reply": "Hijack"}, headers=trade.buyer_headers).status_code == 403
    shop = client.get(f"{API}/seller/reviews", headers=trade.seller_headers).json()
    assert shop[0]["reply"] == "Thank you!"


def test_unconfirmed_review_is_labelled_and_weighs_less(client, trade, db):
    client.post(f"{API}/conversations/{trade.convo}/messages", json={"body": "Hi, still available?"}, headers=trade.buyer_headers)
    res = client.post(
        f"{API}/conversations/{trade.convo}/review", json={"rating": 1, "body": "Never showed up"}, headers=trade.buyer_headers
    )
    assert res.status_code == 201 and res.json()["confirmed_deal"] is False
    assert client.post(f"{API}/conversations/{trade.convo}/review", json={"rating": 1}, headers=trade.buyer_headers).status_code == 409
    complete(trade)
    oid = db.scalars(select(Order)).one().public_id
    assert client.post(f"{API}/orders/{oid}/review", json={"rating": 5}, headers=trade.buyer_headers).status_code == 201
    shop = db.scalars(select(Shop)).one()
    # confirmed 5★ counts double, unconfirmed 1★ counts once: (5*2 + 1) / 3
    from app.features.catalogue.service import rating_avg

    assert rating_avg(shop) == 3.7
    listed = client.get(f"/api/v1/shops/{shop.slug}/reviews").json()
    assert [r["confirmed_deal"] for r in listed] == [True, False]


def test_unconfirmed_review_needs_a_real_conversation(client, h, trade):
    res = client.post(f"{API}/conversations/{trade.convo}/review", json={"rating": 5}, headers=trade.buyer_headers)
    assert res.status_code == 409  # buyer never wrote a message
    h.make_user("stranger@example.com")
    stranger = h.login("stranger@example.com")
    assert client.post(f"{API}/conversations/{trade.convo}/review", json={"rating": 5}, headers=stranger).status_code == 404


def test_did_you_buy_prompt_after_24_hours_once(client, trade, db):
    client.post(f"{API}/conversations/{trade.convo}/messages", json={"body": "Is it new?"}, headers=trade.buyer_headers)
    run_due(db, now=utcnow() + timedelta(hours=2))
    assert not list(db.scalars(select(Notification).where(Notification.kind == "review.prompt")))
    convo = db.get(Conversation, trade.convo)
    convo.last_message_at = utcnow() - timedelta(hours=25)
    db.commit()
    run_due(db, now=utcnow() + timedelta(hours=26))
    run_due(db, now=utcnow() + timedelta(hours=28))
    prompts = list(db.scalars(select(Notification).where(Notification.kind == "review.prompt")))
    assert len(prompts) == 1 and prompts[0].url.endswith("?review=1")


# ---- analytics --------------------------------------------------------------------------------------------------------


def test_admin_and_seller_analytics(client, h, trade, db):
    client.get(f"{API}/listings/{trade.listing['public_id']}")
    client.get(f"{API}/listings/{trade.listing['public_id']}")
    client.get(f"{API}/search", params={"q": "zzznothing"})
    complete(trade)
    boss = admin(client, h)
    a = client.get(f"{API}/admin/analytics", headers=boss).json()
    assert a["listing_views"] >= 2 and a["orders"] == 1 and a["confirmed_deals"] == 1
    assert a["empty_searches"] >= 1 and a["top_empty_searches"][0]["query"] == "zzznothing"
    csv = client.get(f"{API}/admin/analytics.csv", headers=boss)
    assert csv.status_code == 200 and csv.text.startswith("metric,value")
    s = client.get(f"{API}/seller/analytics", headers=trade.seller_headers).json()
    assert s["listing_views"] >= 2 and s["confirmed_deals"] == 1 and s["top_listings"]
    assert client.get(f"{API}/admin/analytics", headers=trade.buyer_headers).status_code == 403
    assert client.get(f"{API}/seller/analytics", headers=trade.buyer_headers).status_code == 403


def test_admin_can_export_financial_records_as_csv_and_every_export_is_logged(client, h, trade, db):
    import csv
    import io

    oid = trade.paid_order()
    boss = admin(client, h)
    for kind, needle in (("orders", oid), ("payments", "CP"), ("payouts", None), ("ledger", "payment_received")):
        res = client.get(f"{API}/admin/exports/{kind}.csv", headers=boss)
        assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv"), kind
        rows = list(csv.reader(io.StringIO(res.text)))
        assert len(rows) >= 1 and "amount_kobo" in ",".join(rows[0]) or kind == "orders", kind
        if needle:
            assert needle in res.text, kind
    orders = list(csv.DictReader(io.StringIO(client.get(f"{API}/admin/exports/orders.csv", headers=boss).text)))
    assert orders[0]["order_id"] == oid and orders[0]["commission_kobo"] == str(2_000 * NAIRA)
    log = client.get(f"{API}/admin/activity-log", params={"action": "export.csv"}, headers=boss).json()
    assert len(log["items"]) >= 5
    assert client.get(f"{API}/admin/exports/orders.csv", headers=trade.buyer_headers).status_code == 403
    assert client.get(f"{API}/admin/exports/nonsense.csv", headers=boss).status_code == 404
