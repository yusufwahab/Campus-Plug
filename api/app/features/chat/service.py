from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.social import Block, Conversation, Message
from app.models.trust import ContentHide, Report


def get_convo(db: Session, user: User, conversation_id: int) -> Conversation:
    """Participants only. Anyone else gets a 404, so conversation ids cannot be probed."""
    convo = db.get(Conversation, conversation_id)
    if convo is None or user.id not in (convo.buyer_id, convo.seller_user_id):
        raise HTTPException(404, "Conversation not found.")
    return convo


def other_party_id(convo: Conversation, user: User) -> int:
    return convo.seller_user_id if user.id == convo.buyer_id else convo.buyer_id


def is_blocked(db: Session, a: int, b: int) -> bool:
    return (
        db.scalar(
            select(Block.id)
            .where(or_((Block.blocker_id == a) & (Block.blocked_id == b), (Block.blocker_id == b) & (Block.blocked_id == a)))
            .limit(1)
        )
        is not None
    )


def phone_visible(convo: Conversation) -> bool:
    """Phone numbers stay hidden until payment, or until both people agree to share."""
    return convo.phone_unlocked_by_payment or (convo.buyer_shares_phone and convo.seller_shares_phone)


def is_hidden(db: Session, message: Message) -> bool:
    return (
        db.scalar(select(ContentHide.id).where(ContentHide.target_type == "message", ContentHide.target_id == str(message.id)).limit(1))
        is not None
    )


def admin_may_view(db: Session, convo: Conversation) -> bool:
    """Admins can open a private chat only when a message in it was reported or its order is in a dispute."""
    ids = [str(m) for (m,) in db.execute(select(Message.id).where(Message.conversation_id == convo.id)).all()]
    reported = (
        bool(ids) and db.scalar(select(Report.id).where(Report.target_type == "message", Report.target_id.in_(ids)).limit(1)) is not None
    )
    if reported:
        return True
    from app.features.orders.disputes import conversation_in_dispute

    return conversation_in_dispute(db, convo)
