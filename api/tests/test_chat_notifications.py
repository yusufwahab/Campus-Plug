from datetime import timedelta

from sqlalchemy import select

import app.jobs.handlers  # noqa: F401  (registers the scheduled handlers)
from app.adapters.email import LocalEmail
from app.adapters.push import LocalPush
from app.db import utcnow
from app.jobs.core import run_due
from app.models.catalogue import Listing, Shop
from app.models.identity import Location
from app.models.social import Conversation, Notification, PlugRequest, PushSubscription
from tests.test_marketplace import PNG, category_id, listing_body, start_shop

API = "/api/v1"


def verified_seller_with_listing(client, h, db, email="seller@example.com", **over):
    headers, _ = start_shop(client, h, email, over.pop("shop", "Chat Shop"))
    shop = db.scalars(select(Shop).where(Shop.user_id == db.scalar(select(Shop.user_id).order_by(Shop.id.desc())))).one()
    shop.verification_status = "verified"
    db.commit()
    res = client.post(f"{API}/listings", json=listing_body(db, **over), headers=headers)
    return headers, res.json()["public_id"]


def buyer(h, email="buyer@example.com"):
    h.make_user(email)
    return h.login(email)


def open_chat(client, buyer_headers, public_id):
    res = client.post(f"{API}/conversations", json={"listing_id": public_id}, headers=buyer_headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_guest_cannot_chat_and_you_cannot_message_yourself(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    assert client.post(f"{API}/conversations", json={"listing_id": pid}).status_code == 401
    assert client.post(f"{API}/conversations", json={"listing_id": pid}, headers=seller).status_code == 422
    assert client.post(f"{API}/conversations", json={"listing_id": "CP-P-999999"}, headers=buyer(h)).status_code == 404


def test_chat_opens_once_per_listing_and_messages_flow_both_ways(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    assert open_chat(client, b, pid) == cid  # same conversation, not a duplicate
    assert db.query(Conversation).count() == 1

    sent = client.post(f"{API}/conversations/{cid}/messages", json={"body": "Is this still available?"}, headers=b)
    assert sent.status_code == 201 and sent.json()["mine"] is True
    seller_view = client.get(f"{API}/conversations/{cid}/messages", headers=seller).json()
    assert [m["body"] for m in seller_view] == ["Is this still available?"] and seller_view[0]["mine"] is False
    client.post(f"{API}/conversations/{cid}/messages", json={"body": "Yes, come by at 5."}, headers=seller)

    # read receipts: the buyer sees the seller read their message
    buyer_view = client.get(f"{API}/conversations/{cid}/messages", headers=b).json()
    assert [m["read"] for m in buyer_view if m["mine"]] == [True]
    # polling with after_id returns only new messages
    last = buyer_view[-1]["id"]
    assert client.get(f"{API}/conversations/{cid}/messages", params={"after_id": last}, headers=b).json() == []


def test_conversation_list_shows_unread_and_names(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    client.post(f"{API}/conversations/{cid}/messages", json={"body": "Hello"}, headers=b)
    row = client.get(f"{API}/conversations", headers=seller).json()[0]
    assert (row["unread"], row["last_message"], row["other_name"], row["i_am_seller"]) == (1, "Hello", "Buyer", True)
    assert row["listing"]["public_id"] == pid
    assert client.get(f"{API}/conversations", headers=b).json()[0]["other_name"] == "Chat Shop"


def test_only_participants_can_read_or_write(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    stranger = buyer(h, "stranger@example.com")
    for method, path, body in (
        ("get", f"/conversations/{cid}", None),
        ("get", f"/conversations/{cid}/messages", None),
        ("post", f"/conversations/{cid}/messages", {"body": "hi"}),
    ):
        res = client.request(method.upper(), f"{API}{path}", headers=stranger, json=body)
        assert res.status_code == 404, path
    assert client.get(f"{API}/conversations/{cid}/messages").status_code == 401
    assert client.get(f"{API}/conversations", headers=stranger).json() == []


def test_image_messages_are_checked_and_stored(client, h, db, tmp_path, monkeypatch):
    from app.adapters import storage

    monkeypatch.setattr("app.features.chat.router.get_storage", lambda: storage.LocalStorage(tmp_path))
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    assert (
        client.post(f"{API}/conversations/{cid}/images", files={"file": ("x.png", b"not-an-image", "image/png")}, headers=b).status_code
        == 422
    )
    ok = client.post(f"{API}/conversations/{cid}/images", files={"file": ("x.png", PNG, "image/png")}, headers=b)
    assert ok.status_code == 201 and ok.json()["kind"] == "image" and ok.json()["image_url"].startswith("/uploads/")
    assert client.get(f"{API}/conversations", headers=seller).json()[0]["last_message"] == "Photo"


def test_blocking_stops_messages_both_ways_and_can_be_undone(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    assert client.post(f"{API}/conversations/{cid}/block", json={"blocked": True}, headers=seller).json()["blocked"] is True
    assert client.post(f"{API}/conversations/{cid}/messages", json={"body": "hello?"}, headers=b).status_code == 403
    assert client.post(f"{API}/conversations/{cid}/messages", json={"body": "hello?"}, headers=seller).status_code == 403
    client.post(f"{API}/conversations/{cid}/block", json={"blocked": False}, headers=seller)
    assert client.post(f"{API}/conversations/{cid}/messages", json={"body": "hello again"}, headers=b).status_code == 201


def test_blocked_buyer_cannot_open_a_new_chat(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    client.post(f"{API}/conversations/{cid}/block", json={"blocked": True}, headers=seller)
    other_pid = client.post(f"{API}/listings", json=listing_body(db, title="Another item"), headers=seller).json()["public_id"]
    assert client.post(f"{API}/conversations", json={"listing_id": other_pid}, headers=b).status_code == 403


def test_phone_numbers_stay_hidden_until_both_agree(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    from app.models.identity import User

    db.query(User).filter_by(email="buyer@example.com").one().phone = "+2348011111111"
    db.query(User).filter_by(email="seller@example.com").one().phone = "+2348022222222"
    db.commit()
    cid = open_chat(client, b, pid)
    assert client.get(f"{API}/conversations/{cid}", headers=b).json()["phone"] is None
    one_sided = client.post(f"{API}/conversations/{cid}/share-phone", json={"share": True}, headers=b).json()
    assert one_sided["phone"] is None and one_sided["i_share_phone"] is True and one_sided["they_share_phone"] is False
    both = client.post(f"{API}/conversations/{cid}/share-phone", json={"share": True}, headers=seller).json()
    assert both["phone"] == "+2348011111111"  # the seller now sees the buyer's number
    assert client.get(f"{API}/conversations/{cid}", headers=b).json()["phone"] == "+2348022222222"
    client.post(f"{API}/conversations/{cid}/share-phone", json={"share": False}, headers=b)
    assert client.get(f"{API}/conversations/{cid}", headers=seller).json()["phone"] is None


def test_payment_request_is_structured_and_only_for_verified_sellers(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    assert client.post(f"{API}/conversations/{cid}/payment-request", json={"agreed_price_kobo": 200_000}, headers=b).status_code == 403
    res = client.post(
        f"{API}/conversations/{cid}/payment-request",
        json={"agreed_price_kobo": 200_000, "quantity": 2, "delivery_fee_kobo": 50_000, "note": "Two plates"},
        headers=seller,
    )
    assert res.status_code == 201
    msg = res.json()
    assert msg["kind"] == "payment_request"
    assert msg["payload"]["agreed_price_kobo"] == 200_000 and msg["payload"]["listing_id"] == pid and msg["payload"]["status"] == "pending"
    assert client.post(f"{API}/conversations/{cid}/payment-request", json={"agreed_price_kobo": -5}, headers=seller).status_code == 422
    note = db.scalars(select(Notification).where(Notification.kind == "payment.request")).one()
    assert note.essential is True


def test_unverified_seller_cannot_request_payment(client, h, db):
    seller, _ = start_shop(client, h)
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=seller).json()["public_id"]
    b = buyer(h)
    cid = open_chat(client, b, pid)
    res = client.post(f"{API}/conversations/{cid}/payment-request", json={"agreed_price_kobo": 100_000}, headers=seller)
    assert res.status_code == 403 and "Verify" in res.json()["detail"]


def test_admin_can_open_a_chat_only_when_reported_and_every_view_is_logged(client, h, db):
    from app.models.system import ActivityLog

    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    mid = client.post(f"{API}/conversations/{cid}/messages", json={"body": "send me money outside the app"}, headers=seller).json()["id"]
    client.post(f"{API}/conversations/{cid}/messages", json={"body": "ok"}, headers=b)
    h.make_user("boss@example.com", role="admin")
    admin = h.login("boss@example.com")
    assert client.get(f"{API}/admin/conversations/{cid}", params={"reason": "curious"}, headers=admin).status_code == 403
    assert (
        client.post(f"{API}/reports", json={"target_type": "message", "target_id": str(mid), "reason": "scam"}, headers=b).status_code
        == 201
    )
    opened = client.get(f"{API}/admin/conversations/{cid}", params={"reason": "Reviewing scam report"}, headers=admin)
    assert opened.status_code == 200 and len(opened.json()["messages"]) == 2
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "chat.viewed")).one()
    assert (log.reason, log.target_id) == ("Reviewing scam report", str(cid))
    # buyers cannot use the admin view
    assert client.get(f"{API}/admin/conversations/{cid}", params={"reason": "x y z"}, headers=b).status_code == 403


def test_cannot_report_messages_from_chats_you_are_not_in(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    mid = client.post(f"{API}/conversations/{cid}/messages", json={"body": "hello"}, headers=b).json()["id"]
    stranger = buyer(h, "stranger@example.com")
    assert (
        client.post(
            f"{API}/reports", json={"target_type": "message", "target_id": str(mid), "reason": "abuse"}, headers=stranger
        ).status_code
        == 404
    )


def test_hidden_message_is_replaced_for_everyone(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    mid = client.post(f"{API}/conversations/{cid}/messages", json={"body": "abusive words"}, headers=seller).json()["id"]
    client.post(f"{API}/reports", json={"target_type": "message", "target_id": str(mid), "reason": "abuse"}, headers=b)
    h.make_user("boss@example.com", role="admin")
    admin = h.login("boss@example.com")
    rid = client.get(f"{API}/admin/reports", headers=admin).json()[0]["id"]
    client.post(f"{API}/admin/reports/{rid}/resolve", json={"action": "hide", "reason": "Abusive language"}, headers=admin)
    body = client.get(f"{API}/conversations/{cid}/messages", headers=b).json()[0]["body"]
    assert body == "This message was hidden by moderators."


# ---- notifications ------------------------------------------------------------------------------------------------


def test_message_creates_in_app_notification_and_can_be_read(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    for text in ("one", "two", "three"):
        client.post(f"{API}/conversations/{cid}/messages", json={"body": text}, headers=b)
    page = client.get(f"{API}/notifications", headers=seller).json()
    assert page["unread"] == 1  # a burst of messages makes one notification, not three
    assert page["items"][0]["url"] == f"/messages/{cid}"
    nid = page["items"][0]["id"]
    assert client.post(f"{API}/notifications/{nid}/read", headers=b).status_code == 404  # not yours
    assert client.post(f"{API}/notifications/{nid}/read", headers=seller).status_code == 204
    assert client.get(f"{API}/notifications", headers=seller).json()["unread"] == 0
    assert client.get(f"{API}/notifications").status_code == 401


def test_optional_notifications_can_be_turned_off_but_essential_stay_on(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    client.patch(f"{API}/me", json={"notify_optional": False}, headers=seller)
    client.post(f"{API}/conversations/{cid}/messages", json={"body": "hello"}, headers=b)
    assert client.get(f"{API}/notifications", headers=seller).json()["items"] == []
    client.post(f"{API}/conversations/{cid}/payment-request", json={"agreed_price_kobo": 100_000}, headers=seller)
    kinds = [n["kind"] for n in client.get(f"{API}/notifications", headers=b).json()["items"]]
    assert "payment.request" in kinds  # buyer still gets it
    client.patch(f"{API}/me", json={"notify_optional": False}, headers=b)
    client.post(f"{API}/conversations/{cid}/payment-request", json={"agreed_price_kobo": 120_000}, headers=seller)
    assert [n["kind"] for n in client.get(f"{API}/notifications", headers=b).json()["items"]].count("payment.request") == 2


def test_delivery_runs_in_a_background_job_not_in_the_request(client, h, db):
    LocalEmail.outbox.clear()
    LocalPush.outbox.clear()
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    cid = open_chat(client, b, pid)
    client.post(
        f"{API}/push/subscribe",
        json={"endpoint": "https://push.example/abc123456", "p256dh": "key-key-key", "auth": "auth-auth"},
        headers=seller,
    )
    client.post(f"{API}/conversations/{cid}/payment-request", json={"agreed_price_kobo": 100_000}, headers=seller)
    client.post(f"{API}/conversations/{cid}/messages", json={"body": "hello"}, headers=b)
    assert LocalEmail.outbox == [] and LocalPush.outbox == []  # nothing sent during the requests
    result = run_due(db)
    assert result["failed"] == 0 and result["done"] >= 2
    assert [m for m in LocalEmail.outbox if m[0] == "buyer@example.com" and "Payment request" in m[1]]
    assert [p for p in LocalPush.outbox if p["endpoint"].endswith("abc123456") and p["title"].startswith("New message")]
    assert run_due(db)["done"] <= 2  # nothing is delivered twice


def test_push_subscriptions_are_per_user_and_removable(client, h, db):
    b = buyer(h)
    body = {"endpoint": "https://push.example/endpoint-1", "p256dh": "key-key-key", "auth": "auth-auth"}
    assert client.post(f"{API}/push/subscribe", json=body).status_code == 401
    assert client.post(f"{API}/push/subscribe", json=body, headers=b).status_code == 204
    assert client.post(f"{API}/push/subscribe", json=body, headers=b).status_code == 204
    assert db.query(PushSubscription).count() == 1
    assert client.post(f"{API}/push/unsubscribe", json=body, headers=b).status_code == 204
    assert db.query(PushSubscription).count() == 0


# ---- Plug Me ------------------------------------------------------------------------------------------------------


def test_plug_me_request_notifies_matching_sellers_and_they_can_respond(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    b = buyer(h)
    mth = db.scalar(select(Location.id).where(Location.name.like("Madam%")))
    body = {
        "title": "Need a jollof catering tray",
        "description": "For 10 people on Friday",
        "category_id": category_id(db),
        "budget_kobo": 3_000_000,
        "location_id": mth,
    }
    assert client.post(f"{API}/requests", json=body).status_code == 401
    req = client.post(f"{API}/requests", json=body, headers=b)
    assert req.status_code == 201
    rid = req.json()["id"]
    match = [n for n in client.get(f"{API}/notifications", headers=seller).json()["items"] if n["kind"] == "request.match"]
    assert len(match) == 1 and match[0]["url"] == f"/requests/{rid}"
    assert [r["title"] for r in client.get(f"{API}/requests").json()] == ["Need a jollof catering tray"]
    assert client.get(f"{API}/requests").json()[0]["buyer_first_name"] == "Buyer"

    assert (
        client.post(f"{API}/requests/{rid}/respond", json={"message": "I can do that"}, headers=b).status_code == 403
    )  # buyers are not sellers
    chat = client.post(f"{API}/requests/{rid}/respond", json={"message": "I can do that for 25k, ready Friday."}, headers=seller)
    assert chat.status_code == 201
    cid = chat.json()["id"]
    assert client.post(f"{API}/requests/{rid}/respond", json={"message": "again"}, headers=seller).status_code == 409
    assert [m["body"] for m in client.get(f"{API}/conversations/{cid}/messages", headers=b).json()] == [
        "I can do that for 25k, ready Friday."
    ]
    assert client.get(f"{API}/requests/{rid}").json()["responses"] == 1
    reply = [n for n in client.get(f"{API}/notifications", headers=b).json()["items"] if n["kind"] == "request.response"]
    assert reply and reply[0]["url"] == f"/messages/{cid}"


def test_requests_reject_room_numbers_and_past_deadlines(client, h, db):
    b = buyer(h)
    assert client.post(f"{API}/requests", json={"title": "Deliver to Room 204 please", "description": ""}, headers=b).status_code == 422
    past = (utcnow() - timedelta(days=1)).isoformat()
    assert client.post(f"{API}/requests", json={"title": "Need a charger", "deadline": past}, headers=b).status_code == 422


def test_owner_can_close_a_request_and_others_cannot(client, h, db):
    b = buyer(h)
    rid = client.post(f"{API}/requests", json={"title": "Need a desk lamp"}, headers=b).json()["id"]
    other = buyer(h, "other@example.com")
    assert client.post(f"{API}/requests/{rid}/close", headers=other).status_code == 404
    assert client.post(f"{API}/requests/{rid}/close", headers=b).json()["status"] == "closed"
    assert client.get(f"{API}/requests").json() == []
    assert [r["id"] for r in client.get(f"{API}/requests/mine", headers=b).json()] == [rid]


def test_hall_rep_sees_only_requests_in_their_hall(client, h, db):
    from app.models.identity import UserPermission

    mth = db.scalar(select(Location.id).where(Location.name.like("Madam%")))
    fagunwa = db.scalar(select(Location.id).where(Location.name == "Fagunwa"))
    rep = h.make_user("rep@example.com")
    db.add(UserPermission(user_id=rep.id, permission="hall_rep", hall_location_id=mth))
    db.commit()
    b = buyer(h)
    client.post(f"{API}/requests", json={"title": "Need a fan", "location_id": mth}, headers=b)
    client.post(f"{API}/requests", json={"title": "Need a kettle", "location_id": fagunwa}, headers=b)
    rep_headers = h.login("rep@example.com")
    assert [r["title"] for r in client.get(f"{API}/rep/requests", headers=rep_headers).json()] == ["Need a fan"]
    assert client.get(f"{API}/rep/requests", headers=b).status_code == 403


# ---- scheduled jobs -----------------------------------------------------------------------------------------------


def test_expiry_job_expires_listings_reminds_sellers_and_expires_requests(client, h, db):
    seller, pid = verified_seller_with_listing(client, h, db)
    listing = db.scalars(select(Listing)).one()
    listing.expires_at = utcnow() + timedelta(days=2)
    db.commit()
    b = buyer(h)
    rid = client.post(f"{API}/requests", json={"title": "Need a mini fan"}, headers=b).json()["id"]
    db.get(PlugRequest, rid).deadline = utcnow() - timedelta(minutes=1)
    db.commit()

    run_due(db)
    assert [n["kind"] for n in client.get(f"{API}/notifications", headers=seller).json()["items"]].count("listing.expiring") == 1
    assert db.get(PlugRequest, rid).status == "expired"
    run_due(db, now=utcnow() + timedelta(hours=1))
    assert [n["kind"] for n in client.get(f"{API}/notifications", headers=seller).json()["items"]].count(
        "listing.expiring"
    ) == 1  # reminder sent once

    listing.expires_at = utcnow() - timedelta(minutes=5)
    db.commit()
    run_due(db, now=utcnow() + timedelta(hours=2))
    db.refresh(listing)
    assert listing.status == "expired"
    assert "listing.expired" in [n["kind"] for n in client.get(f"{API}/notifications", headers=seller).json()["items"]]
    assert client.get(f"{API}/search", params={"q": "jollof"}).json()["total"] == 0
    assert client.post(f"{API}/listings/{pid}/still-available", headers=seller).json()["status"] == "active"


def test_failed_jobs_retry_with_backoff_then_stop(db):
    from app.jobs import core
    from app.models.system import Job

    calls = []

    @core.handler("always_fails")
    def boom(db_, payload):
        calls.append(1)
        raise RuntimeError("secret detail that must not be stored")

    job = core.enqueue(db, "always_fails", {"token": "s3cret"})
    db.commit()
    now = utcnow()
    for attempt in range(1, core.MAX_ATTEMPTS + 1):
        core.run_due(db, now=now + timedelta(days=attempt))
    db.refresh(job)
    assert (job.status, job.attempts, len(calls)) == ("failed", core.MAX_ATTEMPTS, core.MAX_ATTEMPTS)
    assert job.last_error == "RuntimeError"  # class name only: never messages or payloads
    core.run_due(db, now=now + timedelta(days=30))
    assert len(calls) == core.MAX_ATTEMPTS
    assert db.query(Job).filter_by(kind="always_fails", status="failed").count() == 1
