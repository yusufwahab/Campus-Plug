from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.identity import ADMIN_ROLES, User, UserPermission
from app.security import decode_local_token, decode_supabase_token

DB = Annotated[Session, Depends(get_db)]


def _claims(authorization: str | None) -> dict | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        if get_settings().auth_provider == "supabase":
            return decode_supabase_token(token)
        claims = decode_local_token(token)
        return claims if claims.get("purpose") == "access" else None
    except jwt.PyJWTError:
        return None


def _load_user(db: Session, claims: dict) -> User | None:
    if get_settings().auth_provider == "supabase":
        user = db.scalar(select(User).where(User.auth_id == claims["sub"]))
        if user is None and claims.get("email"):
            # First sign-in through Supabase Auth: provision the matching profile row as a buyer.
            user = User(auth_id=claims["sub"], email=claims["email"], full_name=claims["email"].split("@")[0], role="buyer")
            db.add(user)
            db.commit()
        return user
    return db.get(User, int(claims["sub"]))


def optional_user(db: DB, authorization: Annotated[str | None, Header()] = None) -> User | None:
    claims = _claims(authorization)
    if claims is None:
        return None
    user = _load_user(db, claims)
    if user is None or user.deleted_at is not None or user.status != "active":
        return None
    # Local tokens carry aal=2 after TOTP; Supabase tokens carry "aal2". Not a mapped column.
    user.token_aal = 2 if claims.get("aal") in (2, "aal2") else 1  # type: ignore[attr-defined]
    return user


def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "Please sign in to continue.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required.")
    if getattr(user, "token_aal", 1) < 2:
        raise HTTPException(403, "Two-step sign-in is required for Admin accounts.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_role(*roles: str) -> Callable[[User], User]:
    def dependency(user: CurrentUser) -> User:
        if user.role not in roles and user.role not in ADMIN_ROLES:
            raise HTTPException(403, "You do not have access to this.")
        if user.role in ADMIN_ROLES and getattr(user, "token_aal", 1) < 2:
            raise HTTPException(403, "Two-step sign-in is required for Admin accounts.")
        return user

    return dependency


def get_permission(db: Session, user: User, permission: str) -> UserPermission | None:
    return db.scalar(select(UserPermission).where(UserPermission.user_id == user.id, UserPermission.permission == permission))


def require_permission(permission: str) -> Callable[..., User]:
    """Verifier / Hall Rep add-ons. Admins also pass; nobody else does."""

    def dependency(user: CurrentUser, db: DB) -> User:
        if user.role in ADMIN_ROLES:
            return require_admin(user)
        if get_permission(db, user, permission) is None:
            raise HTTPException(403, f"The {permission.replace('_', ' ')} permission is required.")
        return user

    return dependency


def require_seller(user: CurrentUser) -> User:
    if user.role not in ("seller", *ADMIN_ROLES):
        raise HTTPException(403, "Start a shop to use seller tools.")
    return user


SellerUser = Annotated[User, Depends(require_seller)]
