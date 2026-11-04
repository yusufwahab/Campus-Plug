from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.deps import DB, CurrentUser, SellerUser
from app.features.verification.service import recompute_trust
from app.jobs.core import handler
from app.models.catalogue import Shop
from app.models.commerce import Order
from app.models.growth import Review
from app.models.identity import User
from app.models.social import Conversation, Message, Notification
from app.models.trust import ContentHide
from app.notify import notify
from app.ratelimit import rate_limit

router = APIRouter(tags=["reviews"])


def review_exists(db: Session, order: Order) -> bool:
    return db.scalar(select(Review.id).where(Review.order_id == order.id)) is not None


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str = Field(default="", max_length=1500)


class ReplyIn(BaseModel):
    reply: str = Field(min_length=2, max_length=1000)


class ReviewOut(BaseModel):
    id: int
    rating: int
    body: str
    buyer_first_name: str
    confirmed_deal: bool
    reply: str | None
    created_at: str


def _out(db: Session, r: Review) -> ReviewOut:
    buyer = db.get(User, r.buyer_id)
    return ReviewOut(
        id=r.id,
        rating=r.rating,
        body=r.body,
        buyer_first_name=buyer.full_name.split(" ")[0] if buyer else "Student",
        confirmed_deal=r.confirmed_deal,
        reply=r.reply,
        created_at=r.created_at.isoformat(),
    )


def _apply_to_shop(shop: Shop, review: Review) -> None:
    """Confirmed deals count fully; unconfirmed ones are kept apart and weigh half as much in the displayed rating."""
    if review.confirmed_deal:
        shop.rating_sum += review.rating
        shop.rating_count += 1
    else:
        shop.unconfirmed_sum += review.rating
        shop.unconfirmed_count += 1


def _visible(db: Session, r: Review) -> bool:
    return (
        r.deleted_at is None
        and db.scalar(select(ContentHide.id).where(ContentHide.target_type == "review", ContentHide.target_id == str(r.id)).limit(1))
        is None
    )


@router.post(
    "/orders/{public_id}/review", response_model=ReviewOut, status_code=201, dependencies=[Depends(rate_limit("review", 20, 3600))]
)
def review_order(public_id: str, body: ReviewIn, user: CurrentUser, db: DB) -> ReviewOut:
    """Only completed orders can be reviewed, once, by the buyer."""
    order = db.scalar(select(Order).where(Order.public_id == public_id.upper(), Order.buyer_id == user.id))
    if order is None:
        raise HTTPException(404, "Order not found.")
    if order.status not in ("confirmed", "paid_out"):
        raise HTTPException(409, "You can review an order once it is completed.")
    if review_exists(db, order):
        raise HTTPException(409, "You already reviewed this order.")
    shop = db.get(Shop, order.shop_id)
    if shop is None:
        raise HTTPException(404, "Shop not found.")
    review = Review(order_id=order.id, shop_id=shop.id, buyer_id=user.id, rating=body.rating, body=body.body.strip(), confirmed_deal=True)
    db.add(review)
    _apply_to_shop(shop, review)
    recompute_trust(db, shop)
    notify(db, shop.user_id, "review.new", f"New {body.rating}-star review", body.body[:100], "/seller/reviews")
    db.commit()
    return _out(db, review)


@router.post(
    "/conversations/{conversation_id}/review",
    response_model=ReviewOut,
    status_code=201,
    dependencies=[Depends(rate_limit("review", 20, 3600))],
)
def review_unconfirmed(conversation_id: int, body: ReviewIn, user: CurrentUser, db: DB) -> ReviewOut:
    """For deals that happened outside the app: allowed once per chat, marked Unconfirmed deal and weighted lower."""
    convo = db.get(Conversation, conversation_id)
    if convo is None or convo.buyer_id != user.id:
        raise HTTPException(404, "Conversation not found.")
    if db.scalar(
        select(Order.id).where(Order.conversation_id == convo.id, Order.buyer_id == user.id, Order.status.in_(("confirmed", "paid_out")))
    ):
        raise HTTPException(409, "Review the completed order instead.")
    if db.scalar(select(Review.id).where(Review.conversation_id == convo.id, Review.buyer_id == user.id)):
        raise HTTPException(409, "You already reviewed this seller for this chat.")
    if db.scalar(select(Message.id).where(Message.conversation_id == convo.id, Message.sender_id == user.id).limit(1)) is None:
        raise HTTPException(409, "Start a conversation before reviewing.")
    shop = db.scalar(select(Shop).where(Shop.user_id == convo.seller_user_id))
    if shop is None:
        raise HTTPException(404, "Shop not found.")
    review = Review(
        conversation_id=convo.id, shop_id=shop.id, buyer_id=user.id, rating=body.rating, body=body.body.strip(), confirmed_deal=False
    )
    db.add(review)
    _apply_to_shop(shop, review)
    notify(db, shop.user_id, "review.new", f"New {body.rating}-star review (unconfirmed deal)", body.body[:100], "/seller/reviews")
    db.commit()
    return _out(db, review)


@router.get("/shops/{slug}/reviews", response_model=list[ReviewOut])
def shop_reviews(slug: str, db: DB) -> list[ReviewOut]:
    shop = db.scalar(select(Shop).where(Shop.slug == slug, Shop.deleted_at.is_(None)))
    if shop is None:
        raise HTTPException(404, "Shop not found.")
    rows = db.scalars(select(Review).where(Review.shop_id == shop.id).order_by(Review.confirmed_deal.desc(), Review.id.desc()).limit(100))
    return [_out(db, r) for r in rows if _visible(db, r)]


@router.get("/seller/reviews", response_model=list[ReviewOut])
def my_reviews(user: SellerUser, db: DB) -> list[ReviewOut]:
    shop = db.scalar(select(Shop).where(Shop.user_id == user.id))
    if shop is None:
        return []
    return [_out(db, r) for r in db.scalars(select(Review).where(Review.shop_id == shop.id).order_by(Review.id.desc())) if _visible(db, r)]


@router.post("/reviews/{review_id}/reply", response_model=ReviewOut)
def reply(review_id: int, body: ReplyIn, user: SellerUser, db: DB) -> ReviewOut:
    review = db.get(Review, review_id)
    shop = db.scalar(select(Shop).where(Shop.user_id == user.id))
    if review is None or shop is None or review.shop_id != shop.id:
        raise HTTPException(404, "Review not found.")
    if review.reply is not None:
        raise HTTPException(409, "You can reply to a review only once.")
    review.reply, review.replied_at = body.reply.strip(), utcnow()
    db.commit()
    return _out(db, review)


@handler("did_you_buy_prompts", every=timedelta(hours=1))
def did_you_buy(db: Session, payload: dict) -> None:
    """24 hours after a chat goes quiet with no order, ask the buyer whether they bought from the seller."""
    cutoff = utcnow() - timedelta(hours=24)
    for convo in db.scalars(select(Conversation).where(Conversation.last_message_at <= cutoff, Conversation.listing_id.is_not(None))):
        url = f"/messages/{convo.id}?review=1"
        if db.scalar(select(Notification.id).where(Notification.user_id == convo.buyer_id, Notification.url == url)):
            continue
        sent = db.scalar(select(Message.id).where(Message.conversation_id == convo.id, Message.sender_id == convo.buyer_id).limit(1))
        ordered = db.scalar(select(Order.id).where(Order.conversation_id == convo.id).limit(1))
        reviewed = db.scalar(select(Review.id).where(Review.conversation_id == convo.id).limit(1))
        shop = db.scalar(select(Shop).where(Shop.user_id == convo.seller_user_id))
        if sent and not ordered and not reviewed and shop:
            notify(
                db,
                convo.buyer_id,
                "review.prompt",
                f"Did you buy from {shop.name}?",
                "Tell others how it went. Deals made outside the app show as Unconfirmed.",
                url,
            )
