"""Public content that Admin controls: banned items, announcements and policy text. Plus user reports."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import DB, CurrentUser, OptionalUser
from app.models.catalogue import Listing
from app.models.identity import User
from app.models.trust import Announcement, BannedItem, Policy, Report
from app.ratelimit import rate_limit

router = APIRouter(tags=["content"])


class BannedItemPublic(BaseModel):
    id: int
    name: str
    reason: str
    extra_review: bool


@router.get("/banned-items", response_model=list[BannedItemPublic])
def banned_items(db: DB) -> list[BannedItem]:
    return list(db.scalars(select(BannedItem).order_by(BannedItem.name)))


class AnnouncementPublic(BaseModel):
    id: int
    title: str
    body: str


@router.get("/announcements", response_model=list[AnnouncementPublic])
def announcements(db: DB, user: OptionalUser) -> list[Announcement]:
    audiences = ["all"] + (["sellers"] if user and user.role == "seller" else ["buyers"] if user else [])
    return list(
        db.scalars(
            select(Announcement)
            .where(Announcement.active.is_(True), Announcement.audience.in_(audiences))
            .order_by(Announcement.id.desc())
            .limit(5)
        )
    )


class PolicyOut(BaseModel):
    slug: str
    body: str | None


@router.get("/policies/{slug}", response_model=PolicyOut)
def policy(slug: str, db: DB) -> PolicyOut:
    row = db.get(Policy, slug)
    return PolicyOut(slug=slug, body=row.body if row else None)


class ReportIn(BaseModel):
    target_type: Literal["listing", "user", "message", "review"]
    target_id: str = Field(min_length=1, max_length=40)
    reason: Literal["scam", "banned_item", "abuse", "fake", "wrong_info", "other"]
    details: str = Field(default="", max_length=1000)


class ReportMine(BaseModel):
    id: int
    target_type: str
    target_id: str
    reason: str
    status: str
    resolution: str
    created_at: str


def _mine(r: Report) -> ReportMine:
    return ReportMine(
        id=r.id,
        target_type=r.target_type,
        target_id=r.target_id,
        reason=r.reason,
        status=r.status,
        resolution=r.resolution,
        created_at=r.created_at.isoformat(),
    )


@router.post("/reports", response_model=ReportMine, status_code=201, dependencies=[Depends(rate_limit("report", 10, 3600))])
def create_report(body: ReportIn, user: CurrentUser, db: DB) -> ReportMine:
    if body.target_type == "listing":
        if db.scalar(select(Listing.id).where(Listing.public_id == body.target_id.upper())) is None:
            raise HTTPException(404, "That listing does not exist.")
        body.target_id = body.target_id.upper()
    elif body.target_type == "user":
        if not body.target_id.isdigit() or db.get(User, int(body.target_id)) is None:
            raise HTTPException(404, "That user does not exist.")
        if int(body.target_id) == user.id:
            raise HTTPException(422, "You cannot report yourself.")
    elif body.target_type == "message":
        from app.models.social import Conversation, Message

        message = db.get(Message, int(body.target_id)) if body.target_id.isdigit() else None
        convo = db.get(Conversation, message.conversation_id) if message else None
        if convo is None or user.id not in (convo.buyer_id, convo.seller_user_id):
            raise HTTPException(404, "That message does not exist.")
    existing = db.scalar(
        select(Report.id).where(
            Report.reporter_id == user.id,
            Report.target_type == body.target_type,
            Report.target_id == body.target_id,
            Report.status == "open",
        )
    )
    if existing:
        raise HTTPException(409, "You have already reported this. We are reviewing it.")
    report = Report(reporter_id=user.id, **body.model_dump())
    db.add(report)
    db.commit()
    return _mine(report)


@router.get("/reports", response_model=list[ReportMine])
def my_reports(user: CurrentUser, db: DB) -> list[ReportMine]:
    return [_mine(r) for r in db.scalars(select(Report).where(Report.reporter_id == user.id).order_by(Report.id.desc()))]
