from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import get_settings
from app.db import utcnow
from app.deps import DB, CurrentUser
from app.models.social import Notification, PushSubscription

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    url: str
    essential: bool
    read: bool
    created_at: str


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    unread: int


@router.get("/notifications", response_model=NotificationPage)
def list_notifications(user: CurrentUser, db: DB, limit: int = 50) -> NotificationPage:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(min(limit, 100)))
    unread = (
        db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
        or 0
    )
    items = [
        NotificationOut(
            id=n.id,
            kind=n.kind,
            title=n.title,
            body=n.body,
            url=n.url,
            essential=n.essential,
            read=n.read_at is not None,
            created_at=n.created_at.isoformat(),
        )
        for n in rows
    ]
    return NotificationPage(items=items, unread=unread)


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(notification_id: int, user: CurrentUser, db: DB) -> None:
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    note.read_at = note.read_at or utcnow()
    db.commit()


@router.post("/notifications/read-all", status_code=204)
def mark_all_read(user: CurrentUser, db: DB) -> None:
    for note in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))):
        note.read_at = utcnow()
    db.commit()


class PushIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=600)
    p256dh: str = Field(min_length=5, max_length=200)
    auth: str = Field(min_length=5, max_length=100)


@router.get("/push/public-key")
def public_key() -> dict[str, str]:
    return {"key": get_settings().vapid_public_key}


@router.post("/push/subscribe", status_code=204)
def subscribe(body: PushIn, user: CurrentUser, db: DB) -> None:
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    if existing is None:
        db.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=body.p256dh, auth=body.auth))
    else:
        existing.user_id, existing.p256dh, existing.auth = user.id, body.p256dh, body.auth
    db.commit()


@router.post("/push/unsubscribe", status_code=204)
def unsubscribe(body: PushIn, user: CurrentUser, db: DB) -> None:
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == user.id))
    if existing is not None:
        db.delete(existing)
        db.commit()
