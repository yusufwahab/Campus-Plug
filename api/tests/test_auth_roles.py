import pyotp

from app.models.identity import UserPermission
from app.models.system import ActivityLog

API = "/api/v1"


def signup(client, email="ada@example.com", phone="08031234567"):
    return client.post(f"{API}/auth/signup", json={"email": email, "password": "password123", "full_name": "Ada Obi", "phone": phone})


def test_signup_login_me(client):
    res = signup(client)
    assert res.status_code == 201
    token = res.json()["token"]
    me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "ada@example.com"
    assert me["role"] == "buyer"
    assert me["phone"] == "+2348031234567"
    assert me["phone_verified"] is False
    assert client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "password123"}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "wrong-pass"}).status_code == 401


def test_duplicate_email_and_bad_phone_rejected(client):
    assert signup(client).status_code == 201
    assert signup(client).status_code == 409
    assert signup(client, email="x@example.com", phone="123").status_code == 422


def test_login_is_rate_limited(client):
    for _ in range(10):
        client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "password123"}).status_code == 429


def test_phone_verification_flow(client):
    headers = {"Authorization": f"Bearer {signup(client).json()['token']}"}
    sent = client.post(f"{API}/auth/phone/send", json={"phone": "08031234567"}, headers=headers).json()
    assert (
        client.post(
            f"{API}/auth/phone/verify", json={"code": "000000" if sent["dev_code"] != "000000" else "111111"}, headers=headers
        ).status_code
        == 400
    )
    assert client.post(f"{API}/auth/phone/verify", json={"code": sent["dev_code"]}, headers=headers).status_code == 200
    assert client.get(f"{API}/me", headers=headers).json()["phone_verified"] is True


def test_phone_code_is_single_use_and_locks_after_attempts(client):
    headers = {"Authorization": f"Bearer {signup(client).json()['token']}"}
    sent = client.post(f"{API}/auth/phone/send", json={"phone": "08031234567"}, headers=headers).json()
    wrong = "111111" if sent["dev_code"] != "111111" else "222222"
    for _ in range(5):
        client.post(f"{API}/auth/phone/verify", json={"code": wrong}, headers=headers)
    assert client.post(f"{API}/auth/phone/verify", json={"code": sent["dev_code"]}, headers=headers).status_code == 400


def test_onboarding_validates_campus_and_location(client, db):
    headers = {"Authorization": f"Bearer {signup(client).json()['token']}"}
    campuses = client.get(f"{API}/campuses").json()
    assert [c["slug"] for c in campuses] == ["unilag"]
    locs = client.get(f"{API}/locations").json()
    assert len(locs) == 17 and locs[0]["name"] == "Madam Tinubu Hall (MTH)"
    ok = client.post(
        f"{API}/me/onboarding", json={"campus_id": campuses[0]["id"], "location_id": locs[0]["id"], "interests": ["food"]}, headers=headers
    )
    assert ok.status_code == 200 and ok.json()["onboarded"] is True
    assert client.post(f"{API}/me/onboarding", json={"campus_id": 999}, headers=headers).status_code == 422


def test_all_categories_seeded(client):
    names = [c["name"] for c in client.get(f"{API}/categories").json()]
    assert names == ["Food", "Fashion", "Beauty", "Gadgets", "Services", "Accessories", "Academic", "Others"]


def test_guest_is_blocked(client):
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/admin/users").status_code == 401


def test_buyer_cannot_use_admin_endpoints(client, h):
    h.make_user("buyer@example.com")
    headers = h.login("buyer@example.com")
    assert client.get(f"{API}/admin/users", headers=headers).status_code == 403


def test_admin_needs_two_step_sign_in(client, h):
    admin = h.make_user("boss@example.com", role="admin")
    first = client.post(f"{API}/auth/login", json={"email": "boss@example.com", "password": "password123"}).json()
    assert first["token"] is None and first["mfa_required"] is True and first["mfa_enrolled"] is False
    # an mfa token is not a session
    assert client.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {first['mfa_token']}"}).status_code == 401
    secret = client.post(f"{API}/auth/mfa/enroll", json={"mfa_token": first["mfa_token"]}).json()["secret"]
    assert client.post(f"{API}/auth/mfa/verify", json={"mfa_token": first["mfa_token"], "code": "000000"}).status_code == 401
    done = client.post(f"{API}/auth/mfa/verify", json={"mfa_token": first["mfa_token"], "code": pyotp.TOTP(secret).now()}).json()
    headers = {"Authorization": f"Bearer {done['token']}"}
    assert client.get(f"{API}/admin/users", headers=headers).status_code == 200
    db_admin = h.db.get(type(admin), admin.id)
    assert db_admin.mfa_enabled is True


def test_admin_token_without_aal2_is_rejected(client, h):
    from app.security import create_token

    admin = h.make_user("boss@example.com", role="admin")
    weak = create_token(str(admin.id), role="admin", aal=1)
    assert client.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {weak}"}).status_code == 403


def test_two_admins_and_permission_changes_are_logged(client, h):
    h.make_user("a1@example.com", role="admin")
    h.make_user("a2@example.com", role="admin")
    target = h.make_user("rep@example.com")
    headers = h.login("a1@example.com")
    assert h.login("a2@example.com")
    res = client.post(
        f"{API}/admin/users/{target.id}/permissions",
        json={"permission": "hall_rep", "granted": True, "reason": "Hall rep for MTH"},
        headers=headers,
    )
    assert res.status_code == 200 and res.json()["permissions"] == ["hall_rep"]
    log = h.db.query(ActivityLog).one()
    assert (log.action, log.target_id, log.reason) == ("permission.granted", str(target.id), "Hall rep for MTH")
    assert log.actor_id is not None and log.created_at is not None
    assert h.db.query(UserPermission).count() == 1


def test_admin_action_requires_a_reason(client, h):
    h.make_user("a1@example.com", role="admin")
    target = h.make_user("u@example.com")
    headers = h.login("a1@example.com")
    res = client.post(f"{API}/admin/users/{target.id}/status", json={"status": "suspended", "reason": ""}, headers=headers)
    assert res.status_code == 422


def test_add_on_holder_cannot_see_admin(client, h):
    user = h.make_user("ver@example.com")
    h.db.add(UserPermission(user_id=user.id, permission="verifier"))
    h.db.commit()
    assert client.get(f"{API}/admin/users", headers=h.login("ver@example.com")).status_code == 403


def test_suspended_user_cannot_use_old_token(client, h):
    h.make_user("a1@example.com", role="admin")
    target = h.make_user("u@example.com")
    user_headers = h.login("u@example.com")
    assert client.get(f"{API}/me", headers=user_headers).status_code == 200
    client.post(
        f"{API}/admin/users/{target.id}/status", json={"status": "suspended", "reason": "Spam listings"}, headers=h.login("a1@example.com")
    )
    assert client.get(f"{API}/me", headers=user_headers).status_code == 401


def test_account_deletion_anonymises(client, h):
    h.make_user("gone@example.com")
    headers = h.login("gone@example.com")
    assert client.delete(f"{API}/me", headers=headers).status_code == 204
    assert client.get(f"{API}/me", headers=headers).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": "gone@example.com", "password": "password123"}).status_code == 401


def test_password_reset_works_once(client):
    signup(client)
    token = client.post(f"{API}/auth/forgot", json={"email": "ada@example.com"}).json()["dev_token"]
    assert client.post(f"{API}/auth/reset", json={"token": token, "new_password": "brand-new-pass"}).status_code == 204
    assert client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "brand-new-pass"}).status_code == 200
    assert client.post(f"{API}/auth/reset", json={"token": token, "new_password": "another-pass1"}).status_code == 400


def test_forgot_does_not_reveal_unknown_emails(client):
    res = client.post(f"{API}/auth/forgot", json={"email": "ghost@example.com"})
    assert res.status_code == 200 and res.json()["dev_token"] is None
