from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.storage import MAX_BYTES, get_storage, public_url, sniff_image
from app.audit import log_admin_action
from app.db import utcnow
from app.deps import DB, AdminUser, CurrentUser
from app.features.analytics.service import record
from app.features.chat.service import admin_may_view, get_convo, is_blocked, is_hidden, other_party_id, phone_visible
from app.models.catalogue import Listing, ListingImage, Shop
from app.models.identity import User
from app.models.social import Block, Conversation, Message
from app.notify import notify
from app.ratelimit import rate_limit

router = APIRouter(tags=["chat"])


class StartIn(BaseModel):
    listing_id: str


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class PaymentRequestIn(BaseModel):
    agreed_price_kobo: int = Field(gt=0, le=100_000_000)
    quantity: int = Field(default=1, ge=1, le=1000)
    delivery_fee_kobo: int = Field(default=0, ge=0, le=10_000_000)
    note: str = Field(default="", max_length=300)


class MessageOut(BaseModel):
    id: int
    mine: bool
    sender_id: int
    kind: str
    body: str
    image_url: str | None
    payload: dict[str, Any]
    read: bool
    created_at: str


class ListingBrief(BaseModel):
    public_id: str
    title: str
    price_kobo: int
    image_url: str | None


class ConversationOut(BaseModel):
    id: int
    other_user_id: int
    other_name: str
    other_shop_slug: str | None
    listing: ListingBrief | None
    last_message: str
    last_message_at: str
    unread: int
    phone: str | None
    i_share_phone: bool
    they_share_phone: bool
    blocked: bool
    i_am_seller: bool


def _msg_out(db: Session, user: User, m: Message) -> MessageOut:
    hidden = is_hidden(db, m)
    return MessageOut(
        id=m.id,
        mine=m.sender_id == user.id,
        sender_id=m.sender_id,
        kind="text" if hidden else m.kind,
        body="This message was hidden by moderators." if hidden else m.body,
        image_url=None if hidden or not m.image_path else public_url(m.image_path),
        payload={} if hidden else (m.payload or {}),
        read=m.read_at is not None,
        created_at=m.created_at.isoformat(),
    )


def _preview(m: Message | None) -> str:
    if m is None:
        return ""
    return {"image": "Photo", "payment_request": "Payment request"}.get(m.kind, m.body[:80])


def _convo_out(db: Session, user: User, convo: Conversation) -> ConversationOut:
    other = db.get(User, other_party_id(convo, user))
    shop = db.scalar(select(Shop).where(Shop.user_id == other.id)) if other else None
    listing = db.get(Listing, convo.listing_id) if convo.listing_id else None
    brief = None
    if listing:
        img = db.scalar(select(ListingImage.path).where(ListingImage.listing_id == listing.id).order_by(ListingImage.position).limit(1))
        brief = ListingBrief(
            public_id=listing.public_id, title=listing.title, price_kobo=listing.price_kobo, image_url=public_url(img) if img else None
        )
    last = db.scalar(select(Message).where(Message.conversation_id == convo.id).order_by(Message.id.desc()).limit(1))
    unread = (
        db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == convo.id, Message.sender_id != user.id, Message.read_at.is_(None))
        )
        or 0
    )
    i_am_buyer = user.id == convo.buyer_id
    return ConversationOut(
        id=convo.id,
        other_user_id=other.id if other else 0,
        other_name=shop.name if (shop and i_am_buyer) else (other.full_name.split(" ")[0] if other else "Deleted user"),
        other_shop_slug=shop.slug if shop and i_am_buyer else None,
        listing=brief,
        last_message=_preview(last),
        last_message_at=convo.last_message_at.isoformat(),
        unread=unread,
        phone=other.phone if other and phone_visible(convo) else None,
        i_share_phone=convo.buyer_shares_phone if i_am_buyer else convo.seller_shares_phone,
        they_share_phone=convo.seller_shares_phone if i_am_buyer else convo.buyer_shares_phone,
        blocked=is_blocked(db, user.id, other.id) if other else False,
        i_am_seller=not i_am_buyer,
    )


@router.post("/conversations", response_model=ConversationOut, status_code=201, dependencies=[Depends(rate_limit("chat-start", 30, 3600))])
def start(body: StartIn, user: CurrentUser, db: DB) -> ConversationOut:
    listing = db.scalar(
        select(Listing).where(Listing.public_id == body.listing_id.upper(), Listing.deleted_at.is_(None), Listing.status != "removed")
    )
    shop = db.get(Shop, listing.shop_id) if listing else None
    if listing is None or shop is None:
        raise HTTPException(404, "That listing is not available.")
    if shop.user_id == user.id:
        raise HTTPException(422, "This is your own listing.")
    if is_blocked(db, user.id, shop.user_id):
        raise HTTPException(403, "You cannot message this seller.")
    convo = db.scalar(
        select(Conversation).where(
            Conversation.buyer_id == user.id, Conversation.seller_user_id == shop.user_id, Conversation.listing_id == listing.id
        )
    )
    if convo is None:
        convo = Conversation(buyer_id=user.id, seller_user_id=shop.user_id, listing_id=listing.id)
        db.add(convo)
        record(db, "contact", campus_id=listing.campus_id, shop_id=shop.id, listing_id=listing.id, user_id=user.id)
        db.commit()
    return _convo_out(db, user, convo)


@router.get("/conversations", response_model=list[ConversationOut])
def mine(user: CurrentUser, db: DB) -> list[ConversationOut]:
    rows = db.scalars(
        select(Conversation)
        .where((Conversation.buyer_id == user.id) | (Conversation.seller_user_id == user.id))
        .order_by(Conversation.last_message_at.desc())
        .limit(100)
    )
    return [_convo_out(db, user, c) for c in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def detail(conversation_id: int, user: CurrentUser, db: DB) -> ConversationOut:
    return _convo_out(db, user, get_convo(db, user, conversation_id))


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def messages(conversation_id: int, user: CurrentUser, db: DB, after_id: int = 0) -> list[MessageOut]:
    """Also used for polling (after_id). Reading marks the other person's messages as read."""
    convo = get_convo(db, user, conversation_id)
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == convo.id, Message.id > after_id, Message.deleted_at.is_(None))
            .order_by(Message.id)
            .limit(200)
        )
    )
    changed = False
    for m in db.scalars(
        select(Message).where(Message.conversation_id == convo.id, Message.sender_id != user.id, Message.read_at.is_(None))
    ):
        m.read_at = utcnow()
        changed = True
    if changed:
        db.commit()
    return [_msg_out(db, user, m) for m in rows]


def _post(db: Session, convo: Conversation, user: User, **fields: Any) -> Message:
    other = other_party_id(convo, user)
    if is_blocked(db, user.id, other):
        raise HTTPException(403, "You cannot message this person.")
    msg = Message(conversation_id=convo.id, sender_id=user.id, **fields)
    db.add(msg)
    convo.last_message_at = utcnow()
    db.flush()
    title = {"payment_request": "Payment request", "image": "New photo"}.get(msg.kind, f"New message from {user.full_name.split(' ')[0]}")
    kind = "payment.request" if msg.kind == "payment_request" else "message.new"
    url = f"/messages/{convo.id}"
    unread_note = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == convo.id, Message.sender_id == user.id, Message.read_at.is_(None))
    )
    if kind != "message.new" or (unread_note or 0) <= 1:  # avoid one notification per message in a burst
        notify(db, other, kind, title, _preview(msg), url)
    return msg


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=201,
    dependencies=[Depends(rate_limit("chat-send", 60, 60))],
)
def send(conversation_id: int, body: MessageIn, user: CurrentUser, db: DB) -> MessageOut:
    convo = get_convo(db, user, conversation_id)
    msg = _post(db, convo, user, kind="text", body=body.body.strip())
    db.commit()
    return _msg_out(db, user, msg)


@router.post(
    "/conversations/{conversation_id}/images",
    response_model=MessageOut,
    status_code=201,
    dependencies=[Depends(rate_limit("chat-send", 60, 60))],
)
async def send_image(conversation_id: int, file: Annotated[UploadFile, File()], user: CurrentUser, db: DB) -> MessageOut:
    convo = get_convo(db, user, conversation_id)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "That image is too large (5 MB maximum).")
    ext, _ = sniff_image(data)
    msg = _post(db, convo, user, kind="image", image_path=get_storage().save_public(data, ext))
    db.commit()
    return _msg_out(db, user, msg)


@router.post(
    "/conversations/{conversation_id}/payment-request",
    response_model=MessageOut,
    status_code=201,
    dependencies=[Depends(rate_limit("payment-request", 20, 3600))],
)
def payment_request(conversation_id: int, body: PaymentRequestIn, user: CurrentUser, db: DB) -> MessageOut:
    """The seller sends the agreed price as a structured message; the buyer opens checkout from it."""
    convo = get_convo(db, user, conversation_id)
    if user.id != convo.seller_user_id:
        raise HTTPException(403, "Only the seller can request a payment.")
    shop = db.scalar(select(Shop).where(Shop.user_id == user.id))
    if shop is None or shop.verification_status != "verified":
        raise HTTPException(403, "Verify your identity to receive in-app payments.")
    if shop.payout_review_required:
        raise HTTPException(403, "Your payout details are under review.")
    listing = db.get(Listing, convo.listing_id) if convo.listing_id else None
    if listing is None or listing.status != "active":
        raise HTTPException(409, "This listing is no longer available.")
    payload = {
        "listing_id": listing.public_id,
        "title": listing.title,
        "agreed_price_kobo": body.agreed_price_kobo,
        "quantity": body.quantity,
        "delivery_fee_kobo": body.delivery_fee_kobo,
        "note": body.note,
        "status": "pending",
    }
    msg = _post(db, convo, user, kind="payment_request", body=body.note, payload=payload)
    db.commit()
    return _msg_out(db, user, msg)


class SharePhoneIn(BaseModel):
    share: bool


@router.post("/conversations/{conversation_id}/share-phone", response_model=ConversationOut)
def share_phone(conversation_id: int, body: SharePhoneIn, user: CurrentUser, db: DB) -> ConversationOut:
    """Each person opts in separately. Numbers show only once both have agreed (or after payment)."""
    convo = get_convo(db, user, conversation_id)
    if user.id == convo.buyer_id:
        convo.buyer_shares_phone = body.share
    else:
        convo.seller_shares_phone = body.share
    if body.share and not user.phone:
        raise HTTPException(422, "Add a phone number to your account first.")
    db.commit()
    return _convo_out(db, user, convo)


class BlockIn(BaseModel):
    blocked: bool


@router.post("/conversations/{conversation_id}/block", response_model=ConversationOut)
def block(conversation_id: int, body: BlockIn, user: CurrentUser, db: DB) -> ConversationOut:
    convo = get_convo(db, user, conversation_id)
    other = other_party_id(convo, user)
    existing = db.scalar(select(Block).where(Block.blocker_id == user.id, Block.blocked_id == other))
    if body.blocked and existing is None:
        db.add(Block(blocker_id=user.id, blocked_id=other))
    if not body.blocked and existing is not None:
        db.delete(existing)
    db.commit()
    return _convo_out(db, user, convo)


class AdminChat(BaseModel):
    messages: list[MessageOut]
    participants: list[str]


@router.get("/admin/conversations/{conversation_id}", response_model=AdminChat, tags=["admin"])
def admin_view(conversation_id: int, reason: str, admin: AdminUser, db: DB) -> AdminChat:
    """Private chats can be opened only when reported or in a dispute. Every view is logged with the reason."""
    convo = db.get(Conversation, conversation_id)
    if convo is None:
        raise HTTPException(404, "Conversation not found.")
    if not admin_may_view(db, convo):
        raise HTTPException(403, "This chat has not been reported and is not part of a dispute.")
    log_admin_action(db, admin, "chat.viewed", "conversation", convo.id, reason=reason)
    db.commit()
    rows = db.scalars(select(Message).where(Message.conversation_id == convo.id).order_by(Message.id))
    names = [u.full_name for u in db.scalars(select(User).where(User.id.in_([convo.buyer_id, convo.seller_user_id])))]
    return AdminChat(messages=[_msg_out(db, admin, m) for m in rows], participants=names)
