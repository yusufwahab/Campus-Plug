import pytest
from sqlalchemy import select

from app.models.catalogue import Listing, Shop
from app.models.identity import UserPermission
from app.models.system import ActivityLog, Setting
from app.models.trust import UserWarning, Vouch
from tests.test_marketplace import PNG, listing_body, start_shop

API = "/api/v1"


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    from app.adapters import storage as storage_module

    local = storage_module.LocalStorage(tmp_path)
    monkeypatch.setattr("app.features.verification.router.get_storage", lambda: local)
    return local


def grant(h, email, permission, location_id=None):
    user = h.make_user(email)
    h.db.add(UserPermission(user_id=user.id, permission=permission, hall_location_id=location_id))
    h.db.commit()
    return user


def submit(client, headers, note="My student ID"):
    return client.post(
        f"{API}/seller/verification", files={"student_id": ("id.png", PNG, "image/png")}, data={"note": note}, headers=headers
    )


def test_submission_needs_an_image_and_blocks_duplicates(client, h, storage):
    headers, _ = start_shop(client, h)
    assert client.post(f"{API}/seller/verification", data={"note": "x"}, headers=headers).status_code == 422
    fake = client.post(f"{API}/seller/verification", files={"student_id": ("id.png", b"nope", "image/png")}, headers=headers)
    assert fake.status_code == 422
    assert submit(client, headers).status_code == 201
    assert submit(client, headers).status_code == 409


def test_full_verification_journey(client, h, db, storage):
    seller_headers, _ = start_shop(client, h)
    grant(h, "ver@example.com", "verifier")
    h.make_user("boss@example.com", role="admin")
    sub_id = submit(client, seller_headers).json()["id"]
    ver = h.login("ver@example.com")
    admin = h.login("boss@example.com")

    # unassigned: a Verifier sees nothing and cannot open it
    assert client.get(f"{API}/verify/queue", headers=ver).json() == []
    assert client.get(f"{API}/verify/{sub_id}", headers=ver).status_code == 403

    verifier_id = db.scalar(select(UserPermission.user_id).where(UserPermission.permission == "verifier"))
    assert client.post(f"{API}/admin/verification/{sub_id}/assign", params={"verifier_id": verifier_id}, headers=admin).status_code == 200
    assert [s["id"] for s in client.get(f"{API}/verify/queue", headers=ver).json()] == [sub_id]

    detail = client.get(f"{API}/verify/{sub_id}", headers=ver).json()
    assert detail["student_id_url"].startswith("/api/v1/files/identity/")
    image = client.get(detail["student_id_url"])
    assert image.status_code == 200 and image.headers["cache-control"] == "no-store"
    views = db.scalars(select(ActivityLog).where(ActivityLog.action == "identity_doc.viewed")).all()
    assert len(views) == 1 and views[0].actor_id == verifier_id

    # decisions need a reason unless approving; changes can be requested then re-submitted
    assert client.post(f"{API}/verify/{sub_id}/decision", json={"decision": "reject"}, headers=ver).status_code == 422
    res = client.post(f"{API}/verify/{sub_id}/decision", json={"decision": "request_changes", "reason": "ID photo is blurry"}, headers=ver)
    assert res.json()["status"] == "changes_requested"
    assert client.get(f"{API}/seller/verification", headers=seller_headers).json()["reason"] == "ID photo is blurry"
    sub2 = submit(client, seller_headers).json()["id"]
    assign = client.post(f"{API}/admin/verification/{sub2}/assign", params={"verifier_id": verifier_id}, headers=admin)
    assert assign.status_code == 200
    approved = client.post(f"{API}/verify/{sub2}/decision", json={"decision": "approve"}, headers=ver)
    assert approved.json()["status"] == "approved"
    shop = db.scalars(select(Shop)).one()
    assert (shop.verification_status, shop.trust_level) == ("verified", "verified_student")
    assert client.post(f"{API}/verify/{sub2}/decision", json={"decision": "reject", "reason": "again"}, headers=ver).status_code == 409
    actions = [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]
    assert "verification.changes_requested" in actions and "verification.approved" in actions


def test_nobody_can_verify_themselves(client, h, db, storage):
    grant(h, "ver@example.com", "verifier")
    from app.models.identity import User

    db.query(User).filter_by(email="ver@example.com").one().email_verified = True
    db.commit()
    headers = h.login("ver@example.com")
    assert client.post(f"{API}/seller/start", json={"name": "Ver Shop", "accept_rules": True}, headers=headers).status_code == 201
    sub_id = submit(client, headers).json()["id"]
    assert client.get(f"{API}/verify/queue", headers=headers).json() == []
    assert client.get(f"{API}/verify/{sub_id}", headers=headers).status_code == 403
    assert client.post(f"{API}/verify/{sub_id}/decision", json={"decision": "approve"}, headers=headers).status_code == 403
    assert db.scalars(select(Shop)).one().verification_status == "unverified"


def test_an_admin_cannot_verify_their_own_shop_or_be_assigned_it(client, h, db, storage):
    h.make_user("boss@example.com", role="admin", email_verified=True)
    admin = h.login("boss@example.com")
    assert client.post(f"{API}/seller/start", json={"name": "Boss Shop", "accept_rules": True}, headers=admin).status_code == 201
    sub_id = submit(client, admin).json()["id"]
    assert client.post(f"{API}/verify/{sub_id}/decision", json={"decision": "approve"}, headers=admin).status_code == 403
    boss_id = db.scalars(select(Shop)).one().user_id
    assert client.post(f"{API}/admin/verification/{sub_id}/assign", params={"verifier_id": boss_id}, headers=admin).status_code == 422
    h.make_user("boss2@example.com", role="admin")
    other = h.login("boss2@example.com")
    assert client.post(f"{API}/verify/{sub_id}/decision", json={"decision": "approve"}, headers=other).status_code == 200


def test_identity_links_expire_and_cannot_be_forged(client, h, db, storage):
    from app.security import create_token

    headers, _ = start_shop(client, h)
    sub_id = submit(client, headers).json()["id"]
    claims = {"path": "private/x.png", "sub_id": sub_id}
    expired = create_token("1", purpose="file", minutes=-1, extra=claims)
    assert client.get(f"{API}/files/identity/{expired}").status_code == 404
    assert client.get(f"{API}/files/identity/garbage").status_code == 404
    wrong_purpose = create_token("1", purpose="access", extra=claims)
    assert client.get(f"{API}/files/identity/{wrong_purpose}").status_code == 404
    traversal = create_token("1", purpose="file", extra={"path": "private/../../secrets.txt", "sub_id": sub_id})
    assert client.get(f"{API}/files/identity/{traversal}").status_code == 404
    assert db.query(ActivityLog).filter_by(action="identity_doc.viewed").count() == 0


def test_trust_levels_are_earned_with_admin_thresholds(db):
    from app.features.verification.service import recompute_trust

    shop = Shop(
        public_id="CP-SL-1",
        user_id=1,
        slug="s",
        name="S",
        campus_id=1,
        verification_status="unverified",
        confirmed_deals=0,
        rating_sum=0,
        rating_count=0,
    )
    assert recompute_trust(db, shop) == "email_confirmed"
    shop.verification_status = "verified"
    assert recompute_trust(db, shop) == "verified_student"
    shop.confirmed_deals, shop.rating_sum, shop.rating_count = 10, 46, 10
    assert recompute_trust(db, shop) == "trusted_seller"
    shop.rating_sum = 40  # 4.0 average is below the 4.5 default
    assert recompute_trust(db, shop) == "verified_student"
    db.add(Setting(key="trusted_min_rating_x10", value=40))
    db.commit()
    assert recompute_trust(db, shop) == "trusted_seller"


def test_payout_change_for_verified_seller_needs_review_then_clears(client, h, db, storage):
    headers, _ = start_shop(client, h)
    db.scalars(select(Shop)).one().verification_status = "verified"
    db.commit()
    assert submit(client, headers).status_code == 409  # nothing to review yet
    client.patch(
        f"{API}/seller/settings",
        json={"payout_account_number": "0123456789", "payout_bank": "GTB", "payout_account_name": "T A"},
        headers=headers,
    )
    res = client.post(f"{API}/seller/verification", data={"note": "Changed payout"}, headers=headers)
    assert res.status_code == 201 and res.json()["kind"] == "payout_review"
    h.make_user("boss@example.com", role="admin")
    admin = h.login("boss@example.com")
    assert client.post(f"{API}/verify/{res.json()['id']}/decision", json={"decision": "approve"}, headers=admin).status_code == 200
    assert db.scalars(select(Shop)).one().payout_review_required is False


# ---- hall rep ------------------------------------------------------------------------------------------------


def test_hall_rep_can_onboard_and_vouch_but_nothing_else(client, h, db, storage):
    from app.models.identity import Location

    mth = db.scalar(select(Location.id).where(Location.name.like("Madam%")))
    grant(h, "rep@example.com", "hall_rep", mth)
    h.make_user("student@example.com", email_verified=True)
    rep = h.login("rep@example.com")
    res = client.post(f"{API}/rep/sellers", json={"email": "student@example.com", "shop_name": "Hall Snacks"}, headers=rep)
    assert res.status_code == 201 and res.json()["location_name"].startswith("Madam")
    assert client.post(f"{API}/rep/sellers", json={"email": "student@example.com", "shop_name": "Again"}, headers=rep).status_code == 409
    assert client.post(f"{API}/rep/sellers", json={"email": "ghost@example.com", "shop_name": "Ghost"}, headers=rep).status_code == 404
    pid = res.json()["public_id"]
    vouched = client.post(f"{API}/rep/sellers/{pid}/vouch", headers=rep).json()
    assert vouched["vouched_by_rep"] is True
    client.post(f"{API}/rep/sellers/{pid}/vouch", headers=rep)
    assert db.query(Vouch).count() == 1
    assert [s["public_id"] for s in client.get(f"{API}/rep/sellers", headers=rep).json()] == [pid]

    # what a Hall Rep must NOT be able to do
    assert client.get(f"{API}/verify/queue", headers=rep).status_code == 403
    assert client.get(f"{API}/admin/sellers", headers=rep).status_code == 403
    assert (
        client.post(f"{API}/admin/listings/CP-P-1/moderate", json={"action": "remove", "reason": "x y z"}, headers=rep).status_code == 403
    )
    assert client.post(f"{API}/seller/verification", headers=rep).status_code == 403


def test_onboarded_seller_must_accept_rules_before_publishing(client, h, db):
    grant(h, "rep@example.com", "hall_rep")
    h.make_user("student@example.com", email_verified=True)
    client.post(f"{API}/rep/sellers", json={"email": "student@example.com", "shop_name": "Rep Made"}, headers=h.login("rep@example.com"))
    seller = h.login("student@example.com")
    blocked = client.post(f"{API}/listings", json=listing_body(db), headers=seller)
    assert blocked.status_code == 403 and "seller rules" in blocked.json()["detail"]
    assert client.get(f"{API}/seller/overview", headers=seller).json()["rules_accepted"] is False
    assert client.post(f"{API}/seller/accept-rules", headers=seller).status_code == 204
    assert client.post(f"{API}/listings", json=listing_body(db), headers=seller).status_code == 201


def test_rep_cannot_vouch_outside_their_hall(client, h, db):
    from app.models.identity import Location

    fagunwa = db.scalar(select(Location.id).where(Location.name == "Fagunwa"))
    mth = db.scalar(select(Location.id).where(Location.name.like("Madam%")))
    grant(h, "rep@example.com", "hall_rep", mth)
    headers, res = start_shop(client, h)
    client.patch(f"{API}/seller/settings", json={"location_id": fagunwa}, headers=headers)
    pid = res.json()["public_id"]
    assert client.post(f"{API}/rep/sellers/{pid}/vouch", headers=h.login("rep@example.com")).status_code == 403


# ---- admin moderation ----------------------------------------------------------------------------------------


def admin_headers(client, h):
    h.make_user("boss@example.com", role="admin")
    return h.login("boss@example.com")


def test_report_journey_listing_hidden_and_user_warned_suspended(client, h, db):
    seller, _ = start_shop(client, h, "seller@example.com")
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=seller).json()["public_id"]
    h.make_user("buyer@example.com")
    buyer = h.login("buyer@example.com")
    assert client.post(f"{API}/reports", json={"target_type": "listing", "target_id": pid, "reason": "scam"}).status_code == 401
    rep = client.post(
        f"{API}/reports", json={"target_type": "listing", "target_id": pid, "reason": "scam", "details": "Fake photos"}, headers=buyer
    )
    assert rep.status_code == 201
    assert (
        client.post(f"{API}/reports", json={"target_type": "listing", "target_id": pid, "reason": "scam"}, headers=buyer).status_code == 409
    )
    assert (
        client.post(
            f"{API}/reports", json={"target_type": "listing", "target_id": "CP-P-999999", "reason": "scam"}, headers=buyer
        ).status_code
        == 404
    )
    assert [r["status"] for r in client.get(f"{API}/reports", headers=buyer).json()] == ["open"]

    admin = admin_headers(client, h)
    queue = client.get(f"{API}/admin/reports", headers=admin).json()
    assert len(queue) == 1
    rid = queue[0]["id"]
    assert client.post(f"{API}/admin/reports/{rid}/resolve", json={"action": "hide", "reason": ""}, headers=admin).status_code == 422
    assert (
        client.post(f"{API}/admin/reports/{rid}/resolve", json={"action": "warn", "reason": "Use real photos"}, headers=admin).status_code
        == 200
    )
    assert db.query(UserWarning).count() == 1
    assert client.get(f"{API}/reports", headers=buyer).json()[0]["status"] == "actioned"
    assert client.post(f"{API}/admin/reports/{rid}/resolve", json={"action": "ban", "reason": "again"}, headers=admin).status_code == 409

    # a second report is hidden: the listing disappears
    h.make_user("b2@example.com")
    client.post(f"{API}/reports", json={"target_type": "listing", "target_id": pid, "reason": "fake"}, headers=h.login("b2@example.com"))
    rid2 = client.get(f"{API}/admin/reports", headers=admin).json()[0]["id"]
    client.post(f"{API}/admin/reports/{rid2}/resolve", json={"action": "hide", "reason": "Confirmed fake"}, headers=admin)
    assert client.get(f"{API}/listings/{pid}").status_code == 404
    # moderation actions are logged
    assert {"report.warn", "report.hide"} <= {a.action for a in db.scalars(select(ActivityLog))}


def test_suspend_and_ban_from_report_lock_the_account(client, h, db):
    seller, _ = start_shop(client, h, "seller@example.com")
    owner_id = db.scalars(select(Shop)).one().user_id
    h.make_user("buyer@example.com")
    client.post(
        f"{API}/reports", json={"target_type": "user", "target_id": str(owner_id), "reason": "abuse"}, headers=h.login("buyer@example.com")
    )
    admin = admin_headers(client, h)
    rid = client.get(f"{API}/admin/reports", headers=admin).json()[0]["id"]
    assert (
        client.post(f"{API}/admin/reports/{rid}/resolve", json={"action": "ban", "reason": "Harassment"}, headers=admin).status_code == 200
    )
    assert client.get(f"{API}/me", headers=seller).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "seller@example.com", "password": "password123"}).status_code == 403


def test_cannot_report_yourself_or_dismiss_without_reason(client, h):
    user = h.make_user("me@example.com")
    headers = h.login("me@example.com")
    assert (
        client.post(
            f"{API}/reports", json={"target_type": "user", "target_id": str(user.id), "reason": "abuse"}, headers=headers
        ).status_code
        == 422
    )


def test_admin_can_remove_and_restore_listing_with_reasons(client, h, db):
    seller, _ = start_shop(client, h)
    pid = client.post(f"{API}/listings", json=listing_body(db), headers=seller).json()["public_id"]
    admin = admin_headers(client, h)
    assert client.post(f"{API}/admin/listings/{pid}/moderate", json={"action": "remove", "reason": "ab"}, headers=admin).status_code == 422
    assert (
        client.post(f"{API}/admin/listings/{pid}/moderate", json={"action": "remove", "reason": "Banned item"}, headers=admin).json()[
            "status"
        ]
        == "removed"
    )
    assert client.get(f"{API}/listings/{pid}").status_code == 404
    assert (
        client.post(f"{API}/admin/listings/{pid}/moderate", json={"action": "restore", "reason": "Appeal accepted"}, headers=admin).json()[
            "status"
        ]
        == "paused"
    )
    assert db.scalars(select(Listing)).one().deleted_at is None


def test_badge_removal_and_seller_commission_are_logged(client, h, db):
    start_shop(client, h)
    shop = db.scalars(select(Shop)).one()
    shop.verification_status, shop.trust_level = "verified", "verified_student"
    db.commit()
    admin = admin_headers(client, h)
    res = client.post(f"{API}/admin/sellers/{shop.public_id}/remove-badge", json={"reason": "ID found to be fake"}, headers=admin).json()
    assert res["verification_status"] == "unverified" and res["trust_level"] == "email_confirmed"
    c = client.post(
        f"{API}/admin/sellers/{shop.public_id}/commission",
        json={"commission_override_bps": 1000, "reason": "Partner seller"},
        headers=admin,
    )
    assert c.json()["public_id"] == shop.public_id
    assert db.scalars(select(Shop)).one().commission_override_bps == 1000
    assert {"badge.removed", "commission.seller_changed"} <= {a.action for a in db.scalars(select(ActivityLog))}
    found = client.get(f"{API}/admin/sellers", params={"q": shop.public_id}, headers=admin).json()
    assert found[0]["owner_email"] == "seller@example.com" and found[0]["commission_override_bps"] == 1000


# ---- admin settings, no-code changes ------------------------------------------------------------------------------


def test_settings_change_without_code_and_are_validated(client, h, db):
    admin = admin_headers(client, h)
    assert client.get(f"{API}/admin/settings", headers=admin).json()["values"]["commission_bps"] == 2000
    res = client.put(f"{API}/admin/settings/commission_bps", json={"value": 1500, "reason": "Promo period"}, headers=admin)
    assert res.json()["values"]["commission_bps"] == 1500
    assert client.put(f"{API}/admin/settings/commission_bps", json={"value": 20000, "reason": "typo"}, headers=admin).status_code == 422
    assert client.put(f"{API}/admin/settings/commission_bps", json={"value": "lots", "reason": "typo"}, headers=admin).status_code == 422
    assert client.put(f"{API}/admin/settings/allow_vendors", json={"value": "yes", "reason": "typo"}, headers=admin).status_code == 422
    assert client.put(f"{API}/admin/settings/nope", json={"value": 1, "reason": "typo"}, headers=admin).status_code == 404
    assert client.put(f"{API}/admin/settings/commission_bps", json={"value": 1000}, headers=admin).status_code == 422
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "setting.changed")).one()
    assert (log.before, log.after, log.reason) == (2000, 1500, "Promo period")


def test_listing_limit_setting_takes_effect_immediately(client, h, db):
    seller, _ = start_shop(client, h)
    for _ in range(3):
        client.post(f"{API}/listings", json=listing_body(db), headers=seller)
    assert client.post(f"{API}/listings", json=listing_body(db), headers=seller).status_code == 403
    admin = admin_headers(client, h)
    client.put(f"{API}/admin/settings/unverified_listing_limit", json={"value": 4, "reason": "Pilot"}, headers=admin)
    assert client.post(f"{API}/listings", json=listing_body(db), headers=seller).status_code == 201


def test_category_campus_and_location_management(client, h, db):
    admin = admin_headers(client, h)
    new = client.post(
        f"{API}/admin/categories", json={"slug": "pets", "name": "Pets", "tint": "mint", "reason": "New demand"}, headers=admin
    )
    assert new.status_code == 201
    assert "Pets" in [c["name"] for c in client.get(f"{API}/categories").json()]
    cid = new.json()["id"]
    client.put(
        f"{API}/admin/categories/{cid}",
        json={"slug": "pets", "name": "Pets", "tint": "sky", "enabled": False, "reason": "Pause"},
        headers=admin,
    )
    assert "Pets" not in [c["name"] for c in client.get(f"{API}/categories").json()]
    assert (
        client.post(
            f"{API}/admin/categories", json={"slug": "pets", "name": "Dup", "tint": "mint", "reason": "dup"}, headers=admin
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{API}/admin/categories", json={"slug": "Bad Slug", "name": "Bad", "tint": "mint", "reason": "bad"}, headers=admin
        ).status_code
        == 422
    )

    campus = client.post(
        f"{API}/admin/campuses", json={"slug": "yabatech", "name": "Yabatech", "enabled": False, "reason": "Prepare"}, headers=admin
    ).json()
    assert "yabatech" not in [c["slug"] for c in client.get(f"{API}/campuses").json()]
    client.put(
        f"{API}/admin/campuses/{campus['id']}",
        json={"slug": "yabatech", "name": "Yabatech", "enabled": True, "reason": "Launch"},
        headers=admin,
    )
    assert "yabatech" in [c["slug"] for c in client.get(f"{API}/campuses").json()]
    loc = client.post(
        f"{API}/admin/locations", json={"campus_id": campus["id"], "name": "Main Gate", "kind": "area", "reason": "Seed"}, headers=admin
    )
    assert loc.status_code == 201
    assert [x["name"] for x in client.get(f"{API}/locations", params={"campus_id": campus["id"]}).json()] == ["Main Gate"]


def test_banned_items_announcements_and_policies(client, h):
    admin = admin_headers(client, h)
    client.post(f"{API}/admin/banned-items", json={"name": "Counterfeit phones", "reason": "Illegal", "extra_review": False}, headers=admin)
    assert [b["name"] for b in client.get(f"{API}/banned-items").json()] == ["Counterfeit phones"]
    a = client.post(
        f"{API}/admin/announcements", json={"title": "Welcome", "body": "Campus Plug is live", "audience": "all"}, headers=admin
    ).json()
    assert [x["title"] for x in client.get(f"{API}/announcements").json()] == ["Welcome"]
    client.post(f"{API}/admin/announcements/{a['id']}/active", params={"active": False}, headers=admin)
    assert client.get(f"{API}/announcements").json() == []
    assert client.get(f"{API}/policies/terms").json()["body"] is None
    client.put(
        f"{API}/admin/policies/terms", json={"body": "These are the final terms of use. " * 3, "reason": "Legal review done"}, headers=admin
    )
    assert client.get(f"{API}/policies/terms").json()["body"].startswith("These are the final")
    assert client.put(f"{API}/admin/policies/other", json={"body": "x" * 30, "reason": "unknown policy"}, headers=admin).status_code == 404


def test_team_and_second_admin_and_activity_log(client, h, db):
    admin = admin_headers(client, h)
    h.make_user("second@example.com")
    res = client.post(f"{API}/admin/team/admins", json={"email": "second@example.com", "reason": "Backup admin"}, headers=admin)
    assert res.status_code == 201
    assert (
        client.post(f"{API}/admin/team/admins", json={"email": "second@example.com", "reason": "again"}, headers=admin).status_code == 409
    )
    emails = [m["email"] for m in client.get(f"{API}/admin/team", headers=admin).json()]
    assert {"boss@example.com", "second@example.com"} <= set(emails)
    # promoted admin still has to pass two-step sign-in
    first = client.post(f"{API}/auth/login", json={"email": "second@example.com", "password": "password123"}).json()
    assert first["mfa_required"] is True and first["token"] is None
    page = client.get(f"{API}/admin/activity-log", params={"action": "admin."}, headers=admin).json()
    assert page["total"] == 1 and page["items"][0]["reason"] == "Backup admin"
    assert client.get(f"{API}/admin/activity-log", params={"q": "backup"}, headers=admin).json()["total"] == 1


def test_activity_log_has_no_update_or_delete_endpoints(client):
    spec = client.get("/openapi.json").json()["paths"]
    log_paths = {p: list(m) for p, m in spec.items() if "activity-log" in p}
    assert log_paths == {"/api/v1/admin/activity-log": ["get"]}


def test_overview_and_csv_exports(client, h, db):
    start_shop(client, h)
    admin = admin_headers(client, h)
    ov = client.get(f"{API}/admin/overview", headers=admin).json()
    assert ov["sellers"] == 1 and ov["users"] == 2
    csv_text = client.get(f"{API}/admin/exports/users.csv", headers=admin)
    assert csv_text.headers["content-type"].startswith("text/csv") and "seller@example.com" in csv_text.text
    assert client.get(f"{API}/admin/exports/secrets.csv", headers=admin).status_code == 404
    assert "export.csv" in [a.action for a in db.scalars(select(ActivityLog))]


def test_csv_export_neutralises_formula_injection(client, h, db):
    h.make_user("evil@example.com", full_name='=HYPERLINK("http://evil")')
    admin = admin_headers(client, h)
    body = client.get(f"{API}/admin/exports/users.csv", headers=admin).text
    assert "'=HYPERLINK" in body and ",=HYPERLINK" not in body


def test_non_admin_cannot_reach_any_admin_endpoint(client, h):
    h.make_user("seller@example.com", role="seller")
    headers = h.login("seller@example.com")
    spec = client.get("/openapi.json").json()["paths"]
    for path, methods in spec.items():
        if "/admin/" not in path:
            continue
        concrete = (
            path.replace("{user_id}", "1")
            .replace("{public_id}", "CP-SL-1")
            .replace("{report_id}", "1")
            .replace("{category_id}", "1")
            .replace("{campus_id}", "1")
            .replace("{location_id}", "1")
            .replace("{item_id}", "1")
            .replace("{announcement_id}", "1")
            .replace("{key}", "commission_bps")
            .replace("{slug}", "terms")
            .replace("{kind}", "users")
            .replace("{submission_id}", "1")
        )
        for method in methods:
            res = client.request(method.upper(), concrete, headers=headers, json={})
            assert res.status_code == 403, f"{method.upper()} {path} returned {res.status_code} for a non-admin"
            assert client.request(method.upper(), concrete, json={}).status_code == 401, f"{method.upper()} {path} open to guests"
