from sqlalchemy import select

from app.models.catalogue import Category, Listing, Shop
from app.models.identity import Location
from app.models.system import Setting

API = "/api/v1"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def category_id(db, slug="food"):
    return db.scalar(select(Category.id).where(Category.slug == slug))


def start_shop(client, h, email="seller@example.com", name="Tolu Kitchen", phone_verified=True):
    h.make_user(email, phone_verified=phone_verified)
    headers = h.login(email)
    res = client.post(f"{API}/seller/start", json={"name": name, "accept_rules": True}, headers=headers)
    return headers, res


def listing_body(db, **over):
    body = {
        "type": "product",
        "category_id": category_id(db),
        "title": "Jollof rice and chicken",
        "description": "Freshly made, served hot.",
        "price_kobo": 250_000,
        "condition": "new",
    }
    return {**body, **over}


def test_seller_start_requires_phone_and_rules(client, h):
    _, res = start_shop(client, h, phone_verified=False)
    assert res.status_code == 403
    h.make_user("ok@example.com", phone_verified=True)
    headers = h.login("ok@example.com")
    assert client.post(f"{API}/seller/start", json={"name": "No Rules", "accept_rules": False}, headers=headers).status_code == 422


def test_seller_start_creates_shop_with_platform_id(client, h):
    headers, res = start_shop(client, h)
    assert res.status_code == 201
    body = res.json()
    assert body["public_id"].startswith("CP-SL-") and body["slug"] == "tolu-kitchen"
    assert body["verification_status"] == "unverified" and body["trust_level"] == "phone_confirmed"
    assert client.get(f"{API}/me", headers=headers).json()["role"] == "seller"
    assert client.post(f"{API}/seller/start", json={"name": "Again", "accept_rules": True}, headers=headers).status_code == 409


def test_vendors_disabled_by_default_and_enabled_by_setting(client, h, db):
    h.make_user("v@example.com", phone_verified=True)
    headers = h.login("v@example.com")
    body = {"name": "Vendor Shop", "accept_rules": True, "vendor_type": "vendor"}
    assert client.post(f"{API}/seller/start", json=body, headers=headers).status_code == 403
    db.add(Setting(key="allow_vendors", value=True))
    db.commit()
    assert client.post(f"{API}/seller/start", json=body, headers=headers).status_code == 201


def test_publish_listing_and_guest_can_find_it(client, h, db):
    headers, _ = start_shop(client, h)
    res = client.post(f"{API}/listings", json=listing_body(db), headers=headers)
    assert res.status_code == 201
    listing = res.json()
    assert listing["public_id"].startswith("CP-P-") and listing["status"] == "active"
    found = client.get(f"{API}/search", params={"q": "jollof"}).json()
    assert [c["public_id"] for c in found["listings"]] == [listing["public_id"]]
    assert client.get(f"{API}/search", params={"q": listing["public_id"]}).json()["total"] == 1
    detail = client.get(f"{API}/listings/{listing['public_id']}").json()
    assert detail["seller"]["name"] == "Tolu Kitchen" and detail["price_kobo"] == 250_000


def test_service_listing_gets_service_id(client, h, db):
    headers, _ = start_shop(client, h)
    body = listing_body(db, type="service", category_id=category_id(db, "services"), title="Braiding", condition=None)
    assert client.post(f"{API}/listings", json=body, headers=headers).json()["public_id"].startswith("CP-S-")


def test_room_numbers_are_rejected(client, h, db):
    headers, _ = start_shop(client, h)
    bad = client.post(f"{API}/listings", json=listing_body(db, description="Come to Room 204 in MTH"), headers=headers)
    assert bad.status_code == 422
    ok = client.post(f"{API}/listings", json=listing_body(db, description="Pickup at Madam Tinubu Hall"), headers=headers)
    assert ok.status_code == 201


def test_unverified_listing_limit_is_admin_configurable(client, h, db):
    headers, _ = start_shop(client, h)
    for _ in range(3):
        assert client.post(f"{API}/listings", json=listing_body(db), headers=headers).status_code == 201
    assert client.post(f"{API}/listings", json=listing_body(db), headers=headers).status_code == 403
    db.add(Setting(key="unverified_listing_limit", value=5))
    db.commit()
    assert client.post(f"{API}/listings", json=listing_body(db), headers=headers).status_code == 201
    # drafts never count against the limit
    assert client.post(f"{API}/listings", json=listing_body(db, publish=False), headers=headers).status_code == 201


def test_verified_seller_has_no_limit(client, h, db):
    headers, _ = start_shop(client, h)
    db.scalars(select(Shop)).first().verification_status = "verified"
    db.commit()
    for _ in range(5):
        assert client.post(f"{API}/listings", json=listing_body(db), headers=headers).status_code == 201


def test_high_value_and_selected_categories_need_verification(client, h, db):
    headers, _ = start_shop(client, h)
    expensive = client.post(f"{API}/listings", json=listing_body(db, price_kobo=6_000_000), headers=headers)
    assert expensive.status_code == 403 and "verified" in expensive.json()["detail"]
    db.scalars(select(Category).where(Category.slug == "gadgets")).first().requires_verification = True
    db.commit()
    gadget = client.post(f"{API}/listings", json=listing_body(db, category_id=category_id(db, "gadgets")), headers=headers)
    assert gadget.status_code == 403
    draft = client.post(f"{API}/listings", json=listing_body(db, price_kobo=6_000_000, publish=False), headers=headers)
    assert draft.status_code == 201  # drafts are allowed; publishing is what is gated


def test_seller_cannot_edit_someone_elses_listing(client, h, db):
    a, _ = start_shop(client, h, "a@example.com", "Shop A")
    b, _ = start_shop(client, h, "b@example.com", "Shop B")
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=a).json()["public_id"]
    assert client.patch(f"{API}/listings/{pid}", json={"title": "Hacked title"}, headers=b).status_code == 404
    assert client.post(f"{API}/listings/{pid}/status", json={"status": "removed"}, headers=b).status_code == 404
    assert client.patch(f"{API}/listings/{pid}", json={"title": "My real title"}, headers=a).status_code == 200


def test_buyer_cannot_use_seller_endpoints(client, h):
    h.make_user("buyer@example.com")
    headers = h.login("buyer@example.com")
    assert client.get(f"{API}/seller/listings", headers=headers).status_code == 403
    assert client.post(f"{API}/listings", json={}, headers=headers).status_code in (403, 422)


def test_paused_removed_and_holiday_listings_are_hidden(client, h, db):
    headers, _ = start_shop(client, h)
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=headers).json()["public_id"]
    assert client.get(f"{API}/search", params={"q": "jollof"}).json()["total"] == 1
    client.post(f"{API}/listings/{pid}/status", json={"status": "paused"}, headers=headers)
    assert client.get(f"{API}/search", params={"q": "jollof"}).json()["total"] == 0
    client.post(f"{API}/listings/{pid}/status", json={"status": "active"}, headers=headers)
    client.patch(f"{API}/seller/settings", json={"holiday_mode": True}, headers=headers)
    assert client.get(f"{API}/search", params={"q": "jollof"}).json()["total"] == 0
    assert client.post(f"{API}/listings", json=listing_body(db), headers=headers).status_code == 409
    client.patch(f"{API}/seller/settings", json={"holiday_mode": False}, headers=headers)
    client.post(f"{API}/listings/{pid}/status", json={"status": "removed"}, headers=headers)
    assert client.get(f"{API}/listings/{pid}").status_code == 404


def test_empty_searches_are_recorded_and_offer_ask_campus(client, db):
    res = client.get(f"{API}/search", params={"q": "mechanical keyboard"}).json()
    assert res["total"] == 0 and res["ask_campus"] is True
    from app.models.catalogue import SearchLog

    log = db.scalars(select(SearchLog)).one()
    assert (log.query, log.results) == ("mechanical keyboard", 0)


def test_filters_and_sorting(client, h, db):
    headers, _ = start_shop(client, h)
    client.post(
        f"{API}/listings",
        json=listing_body(db, title="Cheap bag", price_kobo=100_000, category_id=category_id(db, "fashion")),
        headers=headers,
    )
    client.post(
        f"{API}/listings",
        json=listing_body(db, title="Pricey bag", price_kobo=900_000, category_id=category_id(db, "fashion"), condition="used"),
        headers=headers,
    )
    all_ = client.get(f"{API}/listings", params={"category": "fashion", "sort": "price_desc"}).json()
    assert [i["title"] for i in all_["items"]] == ["Pricey bag", "Cheap bag"]
    assert client.get(f"{API}/listings", params={"max_price": 200_000}).json()["total"] == 1
    assert client.get(f"{API}/listings", params={"condition": "used"}).json()["total"] == 1
    assert client.get(f"{API}/listings", params={"verified": "true"}).json()["total"] == 0
    assert client.get(f"{API}/listings", params={"type": "service"}).json()["total"] == 0


def test_relevance_prefers_same_hall_then_verified(client, h, db):
    mth = db.scalar(select(Location.id).where(Location.name.like("Madam%")))
    fagunwa = db.scalar(select(Location.id).where(Location.name == "Fagunwa"))
    a, _ = start_shop(client, h, "a@example.com", "Far Shop")
    b, _ = start_shop(client, h, "b@example.com", "Near Shop")
    client.post(f"{API}/listings", json=listing_body(db, title="Snack far", location_id=fagunwa), headers=a)
    client.post(f"{API}/listings", json=listing_body(db, title="Snack near", location_id=mth), headers=b)
    titles = [i["title"] for i in client.get(f"{API}/listings", params={"location_id": mth}).json()["items"]]
    assert titles[0] == "Snack near"


def test_payout_preview_uses_commission_rules(client, h, db):
    headers, _ = start_shop(client, h)
    p = client.get(
        f"{API}/listings/payout-preview", params={"price_kobo": 1_000_000, "category_id": category_id(db)}, headers=headers
    ).json()
    assert (p["buyer_price_kobo"], p["commission_kobo"], p["seller_payout_kobo"], p["commission_bps"]) == (
        1_000_000,
        200_000,
        800_000,
        2000,
    )
    db.scalars(select(Category)).first().commission_override_bps = 1000
    db.commit()
    p = client.get(
        f"{API}/listings/payout-preview", params={"price_kobo": 1_000_000, "category_id": category_id(db)}, headers=headers
    ).json()
    assert p["commission_kobo"] == 100_000


def test_image_upload_checks_content_and_limit(client, h, db, tmp_path, monkeypatch):
    from app.adapters import storage

    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr("app.features.catalogue.seller.get_storage", lambda: storage.LocalStorage(tmp_path))
    headers, _ = start_shop(client, h)
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=headers).json()["public_id"]
    fake = client.post(f"{API}/listings/{pid}/images", files={"file": ("x.png", b"not an image", "image/png")}, headers=headers)
    assert fake.status_code == 422
    db.add(Setting(key="max_images_per_listing", value=2))
    db.commit()
    for _ in range(2):
        ok = client.post(f"{API}/listings/{pid}/images", files={"file": ("a.png", PNG, "image/png")}, headers=headers)
        assert ok.status_code == 201
    assert client.post(f"{API}/listings/{pid}/images", files={"file": ("a.png", PNG, "image/png")}, headers=headers).status_code == 409
    detail = client.get(f"{API}/listings/{pid}").json()
    assert len(detail["images"]) == 2 and detail["image_url"]


def test_save_and_unsave_requires_sign_in(client, h, db):
    headers, _ = start_shop(client, h)
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=headers).json()["public_id"]
    assert client.put(f"{API}/saved/{pid}").status_code == 401
    assert client.put(f"{API}/saved/{pid}", headers=headers).status_code == 204
    assert [c["public_id"] for c in client.get(f"{API}/saved", headers=headers).json()] == [pid]
    assert client.delete(f"{API}/saved/{pid}", headers=headers).status_code == 204
    assert client.get(f"{API}/saved", headers=headers).json() == []


def test_shop_page_and_home_feed(client, h, db):
    headers, _ = start_shop(client, h)
    client.post(f"{API}/listings", json=listing_body(db), headers=headers)
    client.post(
        f"{API}/listings",
        json=listing_body(db, type="service", category_id=category_id(db, "services"), title="Hair braiding", condition=None),
        headers=headers,
    )
    shop = client.get(f"{API}/shops/tolu-kitchen").json()
    assert len(shop["products"]) == 1 and len(shop["services"]) == 1
    home = client.get(f"{API}/home").json()
    assert len(home["new"]) == 2 and [c["title"] for c in home["open_now"]] == ["Hair braiding"]
    assert client.get(f"{API}/shops/nope").status_code == 404


def test_payout_change_triggers_review_for_verified_seller(client, h, db):
    headers, _ = start_shop(client, h)
    client.patch(
        f"{API}/seller/settings",
        json={"payout_bank": "GTBank", "payout_account_number": "0123456789", "payout_account_name": "Tolu A"},
        headers=headers,
    )
    shop = db.scalars(select(Shop)).first()
    assert shop.payout_review_required is False
    shop.verification_status = "verified"
    db.commit()
    res = client.patch(f"{API}/seller/settings", json={"payout_account_number": "0999999999"}, headers=headers).json()
    assert res["payout_review_required"] is True and res["payout_account_number_masked"] == "******9999"


def test_still_available_renews_expired_listing(client, h, db):
    headers, _ = start_shop(client, h)
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=headers).json()["public_id"]
    listing = db.scalars(select(Listing)).first()
    listing.status = "expired"
    db.commit()
    res = client.post(f"{API}/listings/{pid}/still-available", headers=headers).json()
    assert res["status"] == "active" and res["expires_at"]


def test_contact_form_stores_message_and_is_rate_limited(client, db):
    from app.models.system import ContactMessage

    body = {"name": "Ada", "email": "ada@example.com", "topic": "order", "message": "My order has not arrived yet."}
    assert client.post(f"{API}/contact", json=body).status_code == 201
    assert db.scalars(select(ContactMessage)).one().topic == "order"
    assert client.post(f"{API}/contact", json={**body, "message": "short"}).status_code == 422
    for _ in range(4):
        client.post(f"{API}/contact", json=body)
    assert client.post(f"{API}/contact", json=body).status_code == 429
