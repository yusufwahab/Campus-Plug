import secrets
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.adapters.email import get_email
from app.config import get_settings
from app.db import utcnow
from app.deps import DB, CurrentUser
from app.email_templates import code_email, reset_email
from app.features.auth.schemas import (
    EmailCodeIn,
    ForgotIn,
    LoginIn,
    MfaEnrollIn,
    MfaVerifyIn,
    OnboardingIn,
    PasswordChangeIn,
    ProfileIn,
    ResetIn,
    SignupIn,
    TokenOut,
    UserOut,
)
from app.models.identity import ADMIN_ROLES, Campus, EmailCode, Location, User, UserPermission
from app.ratelimit import rate_limit
from app.security import (
    create_token,
    decode_local_token,
    hash_code,
    hash_password,
    new_totp_secret,
    totp_uri,
    verify_password,
    verify_totp,
)

router = APIRouter(tags=["auth"])


def user_out(db: DB, user: User) -> UserOut:
    perms = list(db.scalars(select(UserPermission.permission).where(UserPermission.user_id == user.id)))
    out = UserOut.model_validate(user)
    out.permissions = perms
    return out


@router.post(
    "/auth/signup",
    response_model=TokenOut,
    status_code=201,
    dependencies=[Depends(rate_limit("signup", 10, 3600))],
)
def signup(body: SignupIn, db: DB) -> TokenOut:
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name, phone=body.phone)
    db.add(user)
    db.commit()
    _send_code(db, user)
    return TokenOut(token=create_token(str(user.id), role=user.role))


@router.post("/auth/login", response_model=TokenOut, dependencies=[Depends(rate_limit("login", 10, 300))])
def login(body: LoginIn, db: DB) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash) or user.deleted_at is not None:
        raise HTTPException(401, "Email or password is incorrect.")
    if user.status != "active":
        raise HTTPException(403, "This account is not active.")
    if user.role in ADMIN_ROLES:
        # Admins never get a full session from a password alone.
        return TokenOut(mfa_required=True, mfa_enrolled=user.mfa_enabled, mfa_token=create_token(str(user.id), purpose="mfa", minutes=10))
    return TokenOut(token=create_token(str(user.id), role=user.role))


def _mfa_user(db: DB, mfa_token: str) -> User:
    try:
        claims = decode_local_token(mfa_token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Your sign-in expired. Start again.") from None
    if claims.get("purpose") != "mfa":
        raise HTTPException(401, "Your sign-in expired. Start again.")
    user = db.get(User, int(claims["sub"]))
    if user is None or user.role not in ADMIN_ROLES:
        raise HTTPException(401, "Your sign-in expired. Start again.")
    return user


@router.post("/auth/mfa/enroll", dependencies=[Depends(rate_limit("mfa", 10, 300))])
def mfa_enroll(body: MfaEnrollIn, db: DB) -> dict[str, str]:
    user = _mfa_user(db, body.mfa_token)
    if user.mfa_enabled:
        raise HTTPException(409, "Two-step sign-in is already set up.")
    user.mfa_secret = new_totp_secret()
    db.commit()
    return {"secret": user.mfa_secret, "uri": totp_uri(user.mfa_secret, user.email)}


@router.post("/auth/mfa/verify", response_model=TokenOut, dependencies=[Depends(rate_limit("mfa", 10, 300))])
def mfa_verify(body: MfaVerifyIn, db: DB) -> TokenOut:
    user = _mfa_user(db, body.mfa_token)
    if not user.mfa_secret or not verify_totp(user.mfa_secret, body.code):
        raise HTTPException(401, "That code is not correct.")
    user.mfa_enabled = True
    db.commit()
    return TokenOut(token=create_token(str(user.id), role=user.role, aal=2, minutes=60 * 8))


def _send_code(db: DB, user: User) -> str:
    """Emails a fresh 6-digit code (Brevo in production). Older unused codes stop working."""
    for old in db.scalars(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.used.is_(False))):
        old.used = True
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailCode(user_id=user.id, email=user.email, code_hash=hash_code(code), expires_at=utcnow() + timedelta(minutes=10)))
    db.commit()
    message = code_email(code)
    get_email().send(user.email, message.subject, message.text, message.html)
    return code


@router.post("/auth/email/send", dependencies=[Depends(rate_limit("email-code", 5, 3600))])
def email_send(user: CurrentUser, db: DB) -> dict[str, str | None]:
    if user.email_verified:
        raise HTTPException(409, "Your email address is already confirmed.")
    code = _send_code(db, user)
    settings = get_settings()
    # TEST ONLY: lets the full flow run without a real mailbox. Never enabled in production.
    exposed = code if settings.expose_dev_codes and not settings.is_production else None
    return {"status": "sent", "dev_code": exposed}


@router.post("/auth/email/verify", dependencies=[Depends(rate_limit("email-verify", 10, 3600))])
def email_verify(body: EmailCodeIn, user: CurrentUser, db: DB) -> dict[str, bool]:
    row = db.scalar(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.used.is_(False)).order_by(EmailCode.id.desc()).limit(1))
    if row is None or row.expires_at < utcnow() or row.attempts >= 5:
        raise HTTPException(400, "That code has expired. Request a new one.")
    row.attempts += 1
    if row.code_hash != hash_code(body.code):
        db.commit()
        raise HTTPException(400, "That code is not correct.")
    row.used = True
    user.email_verified = True
    db.commit()
    return {"email_verified": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser, db: DB) -> UserOut:
    return user_out(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileIn, user: CurrentUser, db: DB) -> UserOut:
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    return user_out(db, user)


@router.post("/me/onboarding", response_model=UserOut)
def onboarding(body: OnboardingIn, user: CurrentUser, db: DB) -> UserOut:
    campus = db.get(Campus, body.campus_id)
    if campus is None or not campus.enabled:
        raise HTTPException(422, "That campus is not available yet.")
    if body.location_id is not None:
        location = db.get(Location, body.location_id)
        if location is None or location.campus_id != campus.id:
            raise HTTPException(422, "That location does not belong to the campus.")
    user.campus_id, user.location_id, user.interests, user.onboarded = campus.id, body.location_id, body.interests, True
    db.commit()
    return user_out(db, user)


@router.post("/me/password", status_code=204)
def change_password(body: PasswordChangeIn, user: CurrentUser, db: DB) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Your current password is not correct.")
    user.password_hash = hash_password(body.new_password)
    db.commit()


@router.delete("/me", status_code=204)
def delete_me(user: CurrentUser, db: DB) -> None:
    from app.features.auth.deletion import open_obligations

    blockers = open_obligations(db, user)
    if blockers:
        raise HTTPException(409, f"You cannot delete your account while you have {blockers}.")
    user.deleted_at = utcnow()
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.phone = None
    user.full_name = "Deleted user"
    user.password_hash = None
    db.commit()


def _reset_fingerprint(user: User) -> str:
    # Changes whenever the password changes, so a reset link works exactly once.
    return hash_code(user.password_hash or "")[:16]


@router.post("/auth/forgot", dependencies=[Depends(rate_limit("forgot", 5, 3600))])
def forgot_password(body: ForgotIn, db: DB) -> dict[str, str | None]:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    link_token = None
    if user is not None and user.deleted_at is None:
        link_token = create_token(str(user.id), purpose="reset", minutes=30) + "." + _reset_fingerprint(user)
        link = f"{get_settings().web_url.rstrip('/')}/reset-password?token={link_token}"
        message = reset_email(link)
        get_email().send(user.email, message.subject, message.text, message.html)
    settings = get_settings()
    # Same response whether or not the email exists, so accounts cannot be probed.
    exposed = link_token if settings.expose_dev_codes and not settings.is_production else None
    return {"status": "sent", "dev_token": exposed}


@router.post("/auth/reset", status_code=204, dependencies=[Depends(rate_limit("reset", 10, 3600))])
def reset_password(body: ResetIn, db: DB) -> None:
    jwt_part, _, fingerprint = body.token.rpartition(".")
    try:
        claims = decode_local_token(jwt_part)
    except jwt.PyJWTError:
        raise HTTPException(400, "This reset link is invalid or has expired.") from None
    user = db.get(User, int(claims["sub"])) if claims.get("purpose") == "reset" else None
    if user is None or user.deleted_at is not None or fingerprint != _reset_fingerprint(user):
        raise HTTPException(400, "This reset link is invalid or has expired.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
