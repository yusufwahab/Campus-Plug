import hashlib
import hmac
from datetime import timedelta
from typing import Any

import bcrypt
import jwt
import pyotp

from app.config import get_settings
from app.db import utcnow

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


def hash_code(code: str) -> str:
    """Short-lived one-time codes (phone). Keyed hash so a database leak does not reveal them."""
    return hmac.new(get_settings().jwt_secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def create_token(
    sub: str, *, purpose: str = "access", role: str = "buyer", aal: int = 1, minutes: int | None = None, extra: dict[str, Any] | None = None
) -> str:
    settings = get_settings()
    ttl = minutes if minutes is not None else settings.access_token_minutes
    claims = {
        "sub": sub,
        "purpose": purpose,
        "role": role,
        "aal": aal,
        "iat": utcnow(),
        "exp": utcnow() + timedelta(minutes=ttl),
        **(extra or {}),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def decode_local_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])


def decode_supabase_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.supabase_jwt_secret, algorithms=[ALGORITHM], audience="authenticated")


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Campus Plug")


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
