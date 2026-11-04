from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.audit import log_admin_action
from app.deps import DB, AdminUser
from app.features.auth.router import user_out
from app.features.auth.schemas import UserOut
from app.models.identity import PERMISSIONS, User, UserPermission
from app.models.system import ActivityLog
from app.notify import notify

router = APIRouter(prefix="/admin", tags=["admin"])


class UserPage(BaseModel):
    items: list[UserOut]
    total: int


class PermissionIn(BaseModel):
    permission: Literal["verifier", "hall_rep"]
    granted: bool
    hall_location_id: int | None = None
    reason: str = Field(min_length=3)


class StatusIn(BaseModel):
    status: Literal["active", "suspended", "banned"]
    reason: str = Field(min_length=3)


@router.get("/users", response_model=UserPage)
def list_users(
    admin: AdminUser, db: DB, q: str = "", role: str = "", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)
) -> UserPage:
    query = select(User).where(User.deleted_at.is_(None))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like), User.phone.like(like)))
    if role:
        query = query.where(User.role == role)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(User.id.desc()).offset((page - 1) * size).limit(size))
    return UserPage(items=[user_out(db, u) for u in rows], total=total)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, admin: AdminUser, db: DB) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user_out(db, user)


@router.post("/users/{user_id}/permissions", response_model=UserOut)
def set_permission(user_id: int, body: PermissionIn, admin: AdminUser, db: DB) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.role in ("admin", "super_admin"):
        raise HTTPException(422, "Admins already have full access.")
    if body.permission not in PERMISSIONS:
        raise HTTPException(422, "Unknown permission")
    existing = db.scalar(select(UserPermission).where(UserPermission.user_id == user.id, UserPermission.permission == body.permission))
    log_admin_action(
        db,
        admin,
        "permission.granted" if body.granted else "permission.revoked",
        "user",
        user.id,
        reason=body.reason,
        before={"had": existing is not None},
        after={"permission": body.permission, "granted": body.granted},
    )
    if body.granted and existing is None:
        db.add(UserPermission(user_id=user.id, permission=body.permission, hall_location_id=body.hall_location_id, granted_by=admin.id))
    if not body.granted and existing is not None:
        db.delete(existing)
    db.commit()
    return user_out(db, user)


@router.post("/users/{user_id}/status", response_model=UserOut)
def set_status(user_id: int, body: StatusIn, admin: AdminUser, db: DB) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(422, "You cannot change your own status.")
    log_admin_action(
        db, admin, f"user.{body.status}", "user", user.id, reason=body.reason, before={"status": user.status}, after={"status": body.status}
    )
    user.status = body.status
    db.commit()
    return user_out(db, user)


class WarnIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class WarningOut(BaseModel):
    created_at: str
    reason: str


@router.post("/users/{user_id}/warn", response_model=UserOut)
def warn_user(user_id: int, body: WarnIn, admin: AdminUser, db: DB) -> UserOut:
    """A formal warning: the person is told why (in the app and by email), and it is kept on their record. The account stays active."""
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(422, "You cannot warn yourself.")
    if user.role in ("admin", "super_admin"):
        raise HTTPException(422, "Admins cannot be warned here.")
    log_admin_action(db, admin, "user.warned", "user", user.id, reason=body.reason)
    notify(db, user.id, "account.warning", "A warning about your account", body.reason, "/account")
    db.commit()
    return user_out(db, user)


@router.get("/users/{user_id}/warnings", response_model=list[WarningOut])
def user_warnings(user_id: int, admin: AdminUser, db: DB) -> list[WarningOut]:
    rows = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.action == "user.warned", ActivityLog.target_type == "user", ActivityLog.target_id == str(user_id))
        .order_by(ActivityLog.id.desc())
    )
    return [WarningOut(created_at=r.created_at.isoformat(), reason=r.reason) for r in rows]
