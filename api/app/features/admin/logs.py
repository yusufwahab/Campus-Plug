import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.audit import log_admin_action
from app.deps import DB, AdminUser
from app.models.catalogue import Listing, SearchLog, Shop
from app.models.identity import ADMIN_ROLES, User, UserPermission
from app.models.system import ActivityLog
from app.models.trust import Report, VerificationSubmission

router = APIRouter(prefix="/admin", tags=["admin"])


class LogRow(BaseModel):
    id: int
    created_at: str
    actor_id: int | None
    action: str
    target_type: str
    target_id: str
    reason: str
    before: Any = None
    after: Any = None


class LogPage(BaseModel):
    items: list[LogRow]
    total: int


@router.get("/activity-log", response_model=LogPage)
def activity_log(
    admin: AdminUser,
    db: DB,
    action: str = "",
    actor_id: int | None = None,
    q: str = "",
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
) -> LogPage:
    query = select(ActivityLog)
    if action:
        query = query.where(ActivityLog.action.like(f"{action}%"))
    if actor_id:
        query = query.where(ActivityLog.actor_id == actor_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(ActivityLog.reason).like(like), func.lower(ActivityLog.target_id).like(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(ActivityLog.id.desc()).offset((page - 1) * size).limit(size))
    items = [
        LogRow(
            id=r.id,
            created_at=r.created_at.isoformat(),
            actor_id=r.actor_id,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            reason=r.reason,
            before=r.before,
            after=r.after,
        )
        for r in rows
    ]
    return LogPage(items=items, total=total)


class Overview(BaseModel):
    users: int
    sellers: int
    verified_sellers: int
    active_listings: int
    pending_verifications: int
    open_reports: int
    searches_without_results: int


@router.get("/overview", response_model=Overview)
def overview(admin: AdminUser, db: DB) -> Overview:
    def count(model: Any, *where: Any) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    return Overview(
        users=count(User, User.deleted_at.is_(None)),
        sellers=count(Shop, Shop.deleted_at.is_(None)),
        verified_sellers=count(Shop, Shop.verification_status == "verified"),
        active_listings=count(Listing, Listing.status == "active", Listing.deleted_at.is_(None)),
        pending_verifications=count(VerificationSubmission, VerificationSubmission.status == "pending"),
        open_reports=count(Report, Report.status == "open"),
        searches_without_results=count(SearchLog, SearchLog.results == 0),
    )


class TeamMember(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    permissions: list[str]


@router.get("/team", response_model=list[TeamMember])
def team(admin: AdminUser, db: DB) -> list[TeamMember]:
    perms: dict[int, list[str]] = {}
    for p in db.scalars(select(UserPermission)):
        perms.setdefault(p.user_id, []).append(p.permission)
    users = db.scalars(
        select(User).where(User.deleted_at.is_(None), or_(User.role.in_(ADMIN_ROLES), User.id.in_(list(perms) or [0]))).order_by(User.id)
    )
    return [TeamMember(id=u.id, email=u.email, full_name=u.full_name, role=u.role, permissions=perms.get(u.id, [])) for u in users]


class AdminInvite(BaseModel):
    email: str
    reason: str


@router.post("/team/admins", response_model=TeamMember, status_code=201)
def make_admin(body: AdminInvite, admin: AdminUser, db: DB) -> TeamMember:
    """Promotes an existing account. They must enrol two-step sign-in the next time they sign in."""
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.deleted_at.is_(None)))
    if user is None:
        raise HTTPException(404, "No account with that email.")
    if user.role in ADMIN_ROLES:
        raise HTTPException(409, "Already an Admin.")
    log_admin_action(db, admin, "admin.granted", "user", user.id, reason=body.reason, before={"role": user.role}, after={"role": "admin"})
    user.role = "admin"
    db.commit()
    return TeamMember(id=user.id, email=user.email, full_name=user.full_name, role=user.role, permissions=[])


def _safe(cell: Any) -> Any:
    """Stops spreadsheet formula injection: cells starting with = + - @ are prefixed with a quote."""
    text = "" if cell is None else str(cell)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@router.get("/exports/{kind}.csv")
def export_csv(kind: str, admin: AdminUser, db: DB) -> Response:
    headers: list[str]
    rows: list[list[Any]]
    if kind == "users":
        headers = ["id", "email", "name", "role", "status", "email_verified", "created_at"]
        rows = [
            [u.id, u.email, u.full_name, u.role, u.status, u.email_verified, u.created_at]
            for u in db.scalars(select(User).where(User.deleted_at.is_(None)))
        ]
    elif kind == "sellers":
        headers = ["shop_id", "name", "verification", "trust_level", "confirmed_deals", "rating_count"]
        rows = [
            [s.public_id, s.name, s.verification_status, s.trust_level, s.confirmed_deals, s.rating_count] for s in db.scalars(select(Shop))
        ]
    elif kind == "listings":
        headers = ["listing_id", "title", "type", "status", "price_kobo", "views", "created_at"]
        rows = [[x.public_id, x.title, x.type, x.status, x.price_kobo, x.views, x.created_at] for x in db.scalars(select(Listing))]
    elif kind == "searches":
        headers = ["query", "results", "created_at"]
        rows = [[x.query, x.results, x.created_at] for x in db.scalars(select(SearchLog))]
    elif kind == "activity-log":
        headers = ["id", "created_at", "actor_id", "action", "target_type", "target_id", "reason"]
        rows = [[x.id, x.created_at, x.actor_id, x.action, x.target_type, x.target_id, x.reason] for x in db.scalars(select(ActivityLog))]
    else:
        raise HTTPException(404, "Unknown export")
    log_admin_action(db, admin, "export.csv", "export", kind, reason=f"Exported {len(rows)} rows")
    db.commit()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(headers)
    writer.writerows([[_safe(c) for c in row] for row in rows])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})
