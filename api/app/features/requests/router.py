from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import utcnow
from app.deps import DB, CurrentUser, OptionalUser, SellerUser, get_permission, require_permission
from app.features.catalogue.schemas import contains_room_number
from app.features.chat.router import ConversationOut, _convo_out
from app.models.catalogue import Category, Listing, Shop
from app.models.identity import Campus, Location, User
from app.models.social import Conversation, Message, PlugRequest, PlugResponse
from app.notify import notify
from app.ratelimit import rate_limit

router = APIRouter(tags=["requests"])

MAX_NOTIFIED_SELLERS = 50


class RequestIn(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(default="", max_length=1500)
    category_id: int | None = None
    budget_kobo: int | None = Field(default=None, gt=0, le=1_000_000_000)
    location_id: int | None = None
    deadline: datetime | None = None


class RequestOut(BaseModel):
    id: int
    title: str
    description: str
    category_name: str | None
    category_slug: str | None
    budget_kobo: int | None
    location_name: str | None
    deadline: str | None
    status: str
    buyer_first_name: str
    responses: int
    mine: bool
    i_responded: bool
    created_at: str


def _out(db: DB, req: PlugRequest, viewer: User | None) -> RequestOut:
    cat = db.get(Category, req.category_id) if req.category_id else None
    loc = db.get(Location, req.location_id) if req.location_id else None
    buyer = db.get(User, req.buyer_id)
    responses = list(db.scalars(select(PlugResponse).where(PlugResponse.request_id == req.id)))
    return RequestOut(
        id=req.id,
        title=req.title,
        description=req.description,
        category_name=cat.name if cat else None,
        category_slug=cat.slug if cat else None,
        budget_kobo=req.budget_kobo,
        location_name=loc.name if loc else None,
        deadline=req.deadline.isoformat() if req.deadline else None,
        status=req.status,
        buyer_first_name=buyer.full_name.split(" ")[0] if buyer else "Student",
        responses=len(responses),
        mine=viewer is not None and viewer.id == req.buyer_id,
        i_responded=viewer is not None and any(r.seller_user_id == viewer.id for r in responses),
        created_at=req.created_at.isoformat(),
    )


@router.post("/requests", response_model=RequestOut, status_code=201, dependencies=[Depends(rate_limit("plug-me", 10, 3600))])
def create(body: RequestIn, user: CurrentUser, db: DB) -> RequestOut:
    if contains_room_number(body.title) or contains_room_number(body.description):
        raise HTTPException(422, "Do not include exact room numbers. Use the hall or area instead.")
    campus_id = user.campus_id or db.scalar(select(Campus.id).where(Campus.enabled.is_(True)).order_by(Campus.id))
    if campus_id is None:
        raise HTTPException(409, "No campus is available yet.")
    if body.category_id is not None and db.get(Category, body.category_id) is None:
        raise HTTPException(422, "Choose a valid category.")
    if body.location_id is not None:
        loc = db.get(Location, body.location_id)
        if loc is None or loc.campus_id != campus_id:
            raise HTTPException(422, "That location does not belong to your campus.")
    if body.deadline is not None and body.deadline <= utcnow():
        raise HTTPException(422, "The deadline must be in the future.")
    req = PlugRequest(buyer_id=user.id, campus_id=campus_id, **body.model_dump())
    db.add(req)
    db.flush()
    # Matching sellers: live listings in the same category on this campus, newest sellers first, capped.
    query = (
        select(Shop.user_id)
        .join(Listing, Listing.shop_id == Shop.id)
        .where(
            Listing.status == "active",
            Listing.deleted_at.is_(None),
            Shop.holiday_mode.is_(False),
            Shop.user_id != user.id,
            Listing.campus_id == campus_id,
        )
    )
    if body.category_id is not None:
        query = query.where(Listing.category_id == body.category_id)
    for seller_user_id in list(dict.fromkeys(db.scalars(query.order_by(Shop.id.desc()).limit(MAX_NOTIFIED_SELLERS * 3))))[
        :MAX_NOTIFIED_SELLERS
    ]:
        notify(db, seller_user_id, "request.match", f"Someone wants: {req.title}", "Reply in chat if you can help.", f"/requests/{req.id}")
    db.commit()
    return _out(db, req, user)


@router.get("/requests", response_model=list[RequestOut])
def feed(db: DB, user: OptionalUser, campus: str = "unilag", category: str | None = None) -> list[RequestOut]:
    """Open requests on a campus. Public: buyers are shown by first name only."""
    query = select(PlugRequest).join(Campus, Campus.id == PlugRequest.campus_id).where(PlugRequest.status == "open", Campus.slug == campus)
    if category:
        query = query.join(Category, Category.id == PlugRequest.category_id).where(Category.slug == category)
    return [_out(db, r, user) for r in db.scalars(query.order_by(PlugRequest.id.desc()).limit(60))]


@router.get("/requests/mine", response_model=list[RequestOut])
def mine(user: CurrentUser, db: DB) -> list[RequestOut]:
    return [
        _out(db, r, user) for r in db.scalars(select(PlugRequest).where(PlugRequest.buyer_id == user.id).order_by(PlugRequest.id.desc()))
    ]


@router.get("/requests/{request_id}", response_model=RequestOut)
def detail(request_id: int, db: DB, user: OptionalUser) -> RequestOut:
    req = db.get(PlugRequest, request_id)
    if req is None:
        raise HTTPException(404, "Request not found.")
    return _out(db, req, user)


class RespondIn(BaseModel):
    message: str = Field(min_length=2, max_length=1000)


@router.post("/requests/{request_id}/respond", response_model=ConversationOut, status_code=201)
def respond(request_id: int, body: RespondIn, user: SellerUser, db: DB) -> ConversationOut:
    """A seller answers a request. This opens a chat with the buyer and sends the first message."""
    req = db.get(PlugRequest, request_id)
    if req is None or req.status != "open":
        raise HTTPException(404, "This request is no longer open.")
    if req.buyer_id == user.id:
        raise HTTPException(422, "This is your own request.")
    if db.scalar(select(PlugResponse.id).where(PlugResponse.request_id == req.id, PlugResponse.seller_user_id == user.id)):
        raise HTTPException(409, "You already responded to this request.")
    convo = Conversation(buyer_id=req.buyer_id, seller_user_id=user.id, request_id=req.id)
    db.add(convo)
    db.flush()
    db.add(Message(conversation_id=convo.id, sender_id=user.id, kind="text", body=body.message.strip()))
    db.add(PlugResponse(request_id=req.id, seller_user_id=user.id, conversation_id=convo.id))
    notify(db, req.buyer_id, "request.response", f'A seller replied to "{req.title}"', body.message[:120], f"/messages/{convo.id}")
    db.commit()
    return _convo_out(db, user, convo)


@router.post("/requests/{request_id}/close", response_model=RequestOut)
def close(request_id: int, user: CurrentUser, db: DB) -> RequestOut:
    req = db.get(PlugRequest, request_id)
    if req is None or req.buyer_id != user.id:
        raise HTTPException(404, "Request not found.")
    req.status = "closed"
    db.commit()
    return _out(db, req, user)


@router.get("/rep/requests", response_model=list[RequestOut], tags=["hall-rep"])
def hall_requests(rep: Annotated[User, Depends(require_permission("hall_rep"))], db: DB) -> list[RequestOut]:
    """Open requests in the Hall Rep's own hall."""
    perm = get_permission(db, rep, "hall_rep")
    if perm is None or perm.hall_location_id is None:
        return []
    rows = db.scalars(
        select(PlugRequest)
        .where(PlugRequest.status == "open", PlugRequest.location_id == perm.hall_location_id)
        .order_by(PlugRequest.id.desc())
    )
    return [_out(db, r, rep) for r in rows]
