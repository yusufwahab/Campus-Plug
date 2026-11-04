from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.storage import MAX_BYTES, get_storage, sniff_image
from app.audit import log_admin_action
from app.db import utcnow
from app.deps import DB, AdminUser, SellerUser, get_permission, require_permission
from app.features.catalogue.seller import my_shop
from app.features.verification.service import recompute_trust
from app.models.catalogue import Shop
from app.models.identity import ADMIN_ROLES, User
from app.models.system import ActivityLog
from app.models.trust import VerificationSubmission
from app.security import create_token, decode_local_token

router = APIRouter(tags=["verification"])

Decision = Literal["approve", "reject", "request_changes"]


class SubmissionOut(BaseModel):
    id: int
    shop_name: str
    shop_public_id: str
    status: str
    reason: str
    note: str
    created_at: str
    assigned_verifier_id: int | None
    kind: str


class SubmissionDetail(SubmissionOut):
    student_id_url: str | None
    seller_name: str


class DecisionIn(BaseModel):
    decision: Decision
    reason: str = Field(default="", max_length=1000)


def _shop(db: Session, sub: VerificationSubmission) -> Shop:
    shop = db.get(Shop, sub.shop_id)
    if shop is None:
        raise HTTPException(404, "Shop not found")
    return shop


def _out(db: Session, sub: VerificationSubmission) -> SubmissionOut:
    shop = _shop(db, sub)
    return SubmissionOut(
        id=sub.id,
        shop_name=shop.name,
        shop_public_id=shop.public_id,
        status=sub.status,
        reason=sub.reason,
        note=sub.note,
        created_at=sub.created_at.isoformat(),
        assigned_verifier_id=sub.assigned_verifier_id,
        kind="identity" if sub.student_id_path else "payout_review",
    )


@router.post("/seller/verification", response_model=SubmissionOut, status_code=201)
async def submit_verification(
    user: SellerUser,
    db: DB,
    student_id: Annotated[UploadFile | None, File()] = None,
    note: Annotated[str, Form(max_length=1000)] = "",
) -> SubmissionOut:
    shop = my_shop(db, user)
    if db.scalar(
        select(VerificationSubmission.id).where(VerificationSubmission.shop_id == shop.id, VerificationSubmission.status == "pending")
    ):
        raise HTTPException(409, "You already have a submission waiting for review.")
    path = ""
    if shop.verification_status == "verified":
        if not shop.payout_review_required:
            raise HTTPException(409, "You are already verified.")
    else:
        if student_id is None:
            raise HTTPException(422, "Upload a photo of your student ID.")
        data = await student_id.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "That image is too large (5 MB maximum).")
        ext, _ = sniff_image(data)
        path = get_storage().save_private(data, ext)
    sub = VerificationSubmission(shop_id=shop.id, student_id_path=path, note=note)
    db.add(sub)
    db.commit()
    return _out(db, sub)


@router.get("/seller/verification", response_model=SubmissionOut | None)
def my_verification(user: SellerUser, db: DB) -> SubmissionOut | None:
    shop = my_shop(db, user)
    sub = db.scalar(
        select(VerificationSubmission).where(VerificationSubmission.shop_id == shop.id).order_by(VerificationSubmission.id.desc()).limit(1)
    )
    return _out(db, sub) if sub else None


Reviewer = Annotated[User, Depends(require_permission("verifier"))]


def _can_see(db: Session, reviewer: User, sub: VerificationSubmission) -> None:
    if _shop(db, sub).user_id == reviewer.id:
        raise HTTPException(403, "Nobody can verify themselves.")
    if reviewer.role not in ADMIN_ROLES and sub.assigned_verifier_id != reviewer.id:
        raise HTTPException(403, "This submission is not assigned to you.")


@router.get("/verify/queue", response_model=list[SubmissionOut])
def queue(reviewer: Reviewer, db: DB, status: str = "pending") -> list[SubmissionOut]:
    query = select(VerificationSubmission).where(VerificationSubmission.status == status).order_by(VerificationSubmission.id)
    if reviewer.role not in ADMIN_ROLES:
        query = query.where(VerificationSubmission.assigned_verifier_id == reviewer.id)
    own_shop = db.scalar(select(Shop.id).where(Shop.user_id == reviewer.id))
    if own_shop:
        query = query.where(VerificationSubmission.shop_id != own_shop)
    return [_out(db, s) for s in db.scalars(query)]


@router.get("/verify/{submission_id}", response_model=SubmissionDetail)
def detail(submission_id: int, reviewer: Reviewer, db: DB) -> SubmissionDetail:
    sub = db.get(VerificationSubmission, submission_id)
    if sub is None:
        raise HTTPException(404, "Submission not found")
    _can_see(db, reviewer, sub)
    owner = db.get(User, _shop(db, sub).user_id)
    link = None
    if sub.student_id_path:
        token = create_token(str(reviewer.id), purpose="file", minutes=5, extra={"path": sub.student_id_path, "sub_id": sub.id})
        link = f"/api/v1/files/identity/{token}"
    return SubmissionDetail(**_out(db, sub).model_dump(), student_id_url=link, seller_name=owner.full_name if owner else "")


@router.get("/files/identity/{token}", include_in_schema=False)
def identity_file(token: str, db: DB) -> Response:
    """Short-lived link to a private identity document. Every successful view is logged."""
    try:
        claims = decode_local_token(token)
    except jwt.PyJWTError:
        raise HTTPException(404, "This link has expired.") from None
    if claims.get("purpose") != "file":
        raise HTTPException(404, "This link has expired.")
    data = get_storage().read_private(claims["path"])
    db.add(
        ActivityLog(
            actor_id=int(claims["sub"]),
            action="identity_doc.viewed",
            target_type="verification",
            target_id=str(claims["sub_id"]),
            reason="Reviewed identity document",
        )
    )
    db.commit()
    _, mime = sniff_image(data)
    return Response(data, media_type=mime, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/verify/{submission_id}/decision", response_model=SubmissionOut)
def decide(submission_id: int, body: DecisionIn, reviewer: Reviewer, db: DB) -> SubmissionOut:
    sub = db.get(VerificationSubmission, submission_id)
    if sub is None:
        raise HTTPException(404, "Submission not found")
    _can_see(db, reviewer, sub)
    if sub.status != "pending":
        raise HTTPException(409, "This submission has already been decided.")
    if body.decision != "approve" and len(body.reason.strip()) < 3:
        raise HTTPException(422, "Give the seller a reason so they know what to fix.")
    shop = _shop(db, sub)
    status = {"approve": "approved", "reject": "rejected", "request_changes": "changes_requested"}[body.decision]
    log_admin_action(
        db,
        reviewer,
        f"verification.{status}",
        "shop",
        shop.public_id,
        reason=body.reason or "Approved after review",
        before={"verification_status": shop.verification_status},
        after={"verification_status": "verified" if status == "approved" else shop.verification_status},
    )
    sub.status, sub.reason, sub.reviewer_id, sub.decided_at = status, body.reason, reviewer.id, utcnow()
    if status == "approved":
        shop.verification_status = "verified"
        shop.payout_review_required = False
        recompute_trust(db, shop)
    db.commit()
    return _out(db, sub)


@router.post("/admin/verification/{submission_id}/assign", response_model=SubmissionOut, tags=["admin"])
def assign(submission_id: int, verifier_id: int, admin: AdminUser, db: DB) -> SubmissionOut:
    sub = db.get(VerificationSubmission, submission_id)
    verifier = db.get(User, verifier_id)
    if sub is None or verifier is None:
        raise HTTPException(404, "Not found")
    if get_permission(db, verifier, "verifier") is None and verifier.role not in ADMIN_ROLES:
        raise HTTPException(422, "That person is not a Verifier.")
    if _shop(db, sub).user_id == verifier.id:
        raise HTTPException(422, "Nobody can verify themselves.")
    log_admin_action(db, admin, "verification.assigned", "verification", sub.id, reason=f"Assigned to verifier {verifier.id}")
    sub.assigned_verifier_id = verifier.id
    db.commit()
    return _out(db, sub)
