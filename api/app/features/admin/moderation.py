from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.audit import log_admin_action
from app.db import utcnow
from app.deps import DB, AdminUser
from app.features.catalogue.schemas import SellerOut
from app.features.catalogue.service import seller_out
from app.features.verification.service import recompute_trust
from app.models.catalogue import Listing, Shop
from app.models.identity import User
from app.models.social import Message
from app.models.trust import ContentHide, Report, UserWarning, VerificationSubmission

router = APIRouter(prefix="/admin", tags=["admin"])


class SellerRow(SellerOut):
    owner_id: int
    owner_email: str
    commission_override_bps: int | None
    listings: int


@router.get("/sellers", response_model=list[SellerRow])
def sellers(
    admin: AdminUser, db: DB, q: str = "", status: str = "", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)
) -> list[SellerRow]:
    query = select(Shop, User).join(User, User.id == Shop.user_id).where(Shop.deleted_at.is_(None))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Shop.name).like(like), func.lower(User.email).like(like), Shop.public_id == q.upper()))
    if status:
        query = query.where(Shop.verification_status == status)
    rows = db.execute(query.order_by(Shop.id.desc()).offset((page - 1) * size).limit(size)).all()
    out = []
    for shop, owner in rows:
        count = db.scalar(select(func.count()).select_from(Listing).where(Listing.shop_id == shop.id, Listing.deleted_at.is_(None))) or 0
        out.append(
            SellerRow(
                **seller_out(db, shop).model_dump(),
                owner_id=owner.id,
                owner_email=owner.email,
                commission_override_bps=shop.commission_override_bps,
                listings=count,
            )
        )
    return out


class BadgeRemoveIn(BaseModel):
    reason: str = Field(min_length=3)


@router.post("/sellers/{public_id}/remove-badge", response_model=SellerOut)
def remove_badge(public_id: str, body: BadgeRemoveIn, admin: AdminUser, db: DB) -> SellerOut:
    shop = db.scalar(select(Shop).where(Shop.public_id == public_id.upper()))
    if shop is None:
        raise HTTPException(404, "Seller not found")
    log_admin_action(
        db, admin, "badge.removed", "shop", shop.public_id, reason=body.reason, before={"verification_status": shop.verification_status}
    )
    shop.verification_status = "unverified"
    recompute_trust(db, shop)
    db.commit()
    return seller_out(db, shop)


class CommissionIn(BaseModel):
    commission_override_bps: int | None = Field(ge=0, le=10_000)
    reason: str = Field(min_length=3)


@router.post("/sellers/{public_id}/commission", response_model=SellerOut)
def seller_commission(public_id: str, body: CommissionIn, admin: AdminUser, db: DB) -> SellerOut:
    """Applies only to new orders; existing orders keep the rate they were created with."""
    shop = db.scalar(select(Shop).where(Shop.public_id == public_id.upper()))
    if shop is None:
        raise HTTPException(404, "Seller not found")
    log_admin_action(
        db, admin, "commission.seller_changed", "shop", shop.public_id, reason=body.reason,
        before={"bps": shop.commission_override_bps}, after={"bps": body.commission_override_bps},
    )  # fmt: skip
    shop.commission_override_bps = body.commission_override_bps
    db.commit()
    return seller_out(db, shop)


class VerificationRow(BaseModel):
    id: int
    shop_name: str
    shop_public_id: str
    status: str
    kind: str
    assigned_verifier_id: int | None
    created_at: str


@router.get("/verification", response_model=list[VerificationRow])
def verification_queue(admin: AdminUser, db: DB, status: str = "pending") -> list[VerificationRow]:
    rows = db.execute(
        select(VerificationSubmission, Shop)
        .join(Shop, Shop.id == VerificationSubmission.shop_id)
        .where(VerificationSubmission.status == status)
        .order_by(VerificationSubmission.id)
    ).all()
    return [
        VerificationRow(
            id=sub.id,
            shop_name=shop.name,
            shop_public_id=shop.public_id,
            status=sub.status,
            kind="identity" if sub.student_id_path else "payout_review",
            assigned_verifier_id=sub.assigned_verifier_id,
            created_at=sub.created_at.isoformat(),
        )
        for sub, shop in rows
    ]


class AdminListing(BaseModel):
    public_id: str
    title: str
    status: str
    price_kobo: int
    shop_name: str
    category_id: int


@router.get("/listings", response_model=list[AdminListing])
def listings(
    admin: AdminUser, db: DB, q: str = "", status: str = "", page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)
) -> list[AdminListing]:
    query = select(Listing, Shop).join(Shop, Shop.id == Listing.shop_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Listing.title).like(like), Listing.public_id == q.upper()))
    if status:
        query = query.where(Listing.status == status)
    rows = db.execute(query.order_by(Listing.id.desc()).offset((page - 1) * size).limit(size)).all()
    return [
        AdminListing(
            public_id=lst.public_id,
            title=lst.title,
            status=lst.status,
            price_kobo=lst.price_kobo,
            shop_name=shop.name,
            category_id=lst.category_id,
        )
        for lst, shop in rows
    ]


class ListingAction(BaseModel):
    action: Literal["remove", "restore"]
    reason: str = Field(min_length=3)


@router.post("/listings/{public_id}/moderate", response_model=AdminListing)
def moderate_listing(public_id: str, body: ListingAction, admin: AdminUser, db: DB) -> AdminListing:
    listing = db.scalar(select(Listing).where(Listing.public_id == public_id.upper()))
    if listing is None:
        raise HTTPException(404, "Listing not found")
    log_admin_action(
        db, admin, f"listing.{body.action}d", "listing", listing.public_id, reason=body.reason, before={"status": listing.status}
    )
    if body.action == "remove":
        listing.status = "removed"
    else:
        listing.status, listing.deleted_at = "paused", None
    db.commit()
    shop = db.get(Shop, listing.shop_id)
    return AdminListing(
        public_id=listing.public_id,
        title=listing.title,
        status=listing.status,
        price_kobo=listing.price_kobo,
        shop_name=shop.name if shop else "",
        category_id=listing.category_id,
    )


class ReportRow(BaseModel):
    id: int
    conversation_id: int | None = None
    target_type: str
    target_id: str
    reason: str
    details: str
    status: str
    resolution: str
    created_at: str


def _report_row(db: DB, r: Report) -> ReportRow:
    conversation_id = None
    if r.target_type == "message" and r.target_id.isdigit():
        message = db.get(Message, int(r.target_id))
        conversation_id = message.conversation_id if message else None
    return ReportRow(
        id=r.id,
        conversation_id=conversation_id,
        target_type=r.target_type,
        target_id=r.target_id,
        reason=r.reason,
        details=r.details,
        status=r.status,
        resolution=r.resolution,
        created_at=r.created_at.isoformat(),
    )


@router.get("/reports", response_model=list[ReportRow])
def reports(admin: AdminUser, db: DB, status: str = "open") -> list[ReportRow]:
    return [_report_row(db, r) for r in db.scalars(select(Report).where(Report.status == status).order_by(Report.id))]


class ReportAction(BaseModel):
    action: Literal["hide", "warn", "suspend", "ban", "dismiss"]
    reason: str = Field(min_length=3)


def _target_user(db: DB, report: Report) -> User | None:
    if report.target_type == "user":
        return db.get(User, int(report.target_id))
    if report.target_type == "listing":
        listing = db.scalar(select(Listing).where(Listing.public_id == report.target_id))
        shop = db.get(Shop, listing.shop_id) if listing else None
        return db.get(User, shop.user_id) if shop else None
    return None


@router.post("/reports/{report_id}/resolve", response_model=ReportRow)
def resolve_report(report_id: int, body: ReportAction, admin: AdminUser, db: DB) -> ReportRow:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    if report.status != "open":
        raise HTTPException(409, "This report has already been handled.")
    target = _target_user(db, report)
    if body.action in ("warn", "suspend", "ban") and (target is None or target.id == admin.id):
        raise HTTPException(422, "That action needs another user as the target.")
    log_admin_action(
        db, admin, f"report.{body.action}", report.target_type, report.target_id, reason=body.reason, after={"report_id": report.id}
    )
    if body.action == "hide":
        if report.target_type == "listing":
            listing = db.scalar(select(Listing).where(Listing.public_id == report.target_id))
            if listing is not None:
                listing.status = "removed"
        else:
            db.add(ContentHide(target_type=report.target_type, target_id=report.target_id))
    elif body.action == "warn" and target is not None:
        db.add(UserWarning(user_id=target.id, reason=body.reason, issued_by=admin.id))
    elif body.action in ("suspend", "ban") and target is not None:
        target.status = "suspended" if body.action == "suspend" else "banned"
    report.status = "dismissed" if body.action == "dismiss" else "actioned"
    report.resolution, report.handled_by, report.handled_at = f"{body.action}: {body.reason}", admin.id, utcnow()
    db.commit()
    return _report_row(db, report)
