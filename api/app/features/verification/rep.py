from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select

from app.deps import DB, get_permission, require_permission
from app.features.catalogue.schemas import SellerOut
from app.features.catalogue.service import seller_out, unique_slug
from app.ids import next_public_id
from app.models.catalogue import Shop
from app.models.identity import Campus, User
from app.models.trust import Vouch

router = APIRouter(prefix="/rep", tags=["hall-rep"])

Rep = Annotated[User, Depends(require_permission("hall_rep"))]


class OnboardIn(BaseModel):
    email: EmailStr
    shop_name: str = Field(min_length=2, max_length=120)


def _hall(db: DB, rep: User) -> int | None:
    perm = get_permission(db, rep, "hall_rep")
    return perm.hall_location_id if perm else None


@router.get("/sellers", response_model=list[SellerOut])
def sellers(rep: Rep, db: DB) -> list[SellerOut]:
    """Sellers this rep onboarded plus sellers based in the rep's hall. Never includes student IDs."""
    hall = _hall(db, rep)
    conditions = [Shop.onboarded_by_id == rep.id]
    if hall:
        conditions.append(Shop.location_id == hall)
    rows = db.scalars(select(Shop).where(or_(*conditions), Shop.deleted_at.is_(None)).order_by(Shop.id.desc()))
    return [seller_out(db, s) for s in rows]


@router.post("/sellers", response_model=SellerOut, status_code=201)
def onboard(body: OnboardIn, rep: Rep, db: DB) -> SellerOut:
    """Opens a shop for a student who already has an account. They accept the seller rules on first sign-in."""
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.deleted_at.is_(None)))
    if user is None:
        raise HTTPException(404, "No account with that email. Ask them to sign up first.")
    if not user.phone_verified:
        raise HTTPException(422, "They need to confirm their phone number first.")
    if db.scalar(select(Shop.id).where(Shop.user_id == user.id)):
        raise HTTPException(409, "They already have a shop.")
    campus_id = user.campus_id or db.scalar(select(Campus.id).where(Campus.enabled.is_(True)).order_by(Campus.id))
    if campus_id is None:
        raise HTTPException(409, "No campus is available yet.")
    shop = Shop(
        public_id=next_public_id(db, "SL"),
        user_id=user.id,
        slug=unique_slug(db, body.shop_name),
        name=body.shop_name,
        campus_id=campus_id,
        location_id=_hall(db, rep) or user.location_id,
        onboarded_by_id=rep.id,
    )
    db.add(shop)
    if user.role == "buyer":
        user.role = "seller"
    db.commit()
    return seller_out(db, shop)


@router.post("/sellers/{public_id}/vouch", response_model=SellerOut)
def vouch(public_id: str, rep: Rep, db: DB) -> SellerOut:
    shop = db.scalar(select(Shop).where(Shop.public_id == public_id.upper(), Shop.deleted_at.is_(None)))
    if shop is None:
        raise HTTPException(404, "Seller not found")
    if shop.user_id == rep.id:
        raise HTTPException(422, "You cannot vouch for yourself.")
    hall = _hall(db, rep)
    if shop.onboarded_by_id != rep.id and not (hall and shop.location_id == hall):
        raise HTTPException(403, "You can only vouch for sellers you onboarded or sellers in your hall.")
    if db.scalar(select(Vouch.id).where(Vouch.hall_rep_id == rep.id, Vouch.shop_id == shop.id)) is None:
        db.add(Vouch(hall_rep_id=rep.id, shop_id=shop.id))
        db.commit()
    return seller_out(db, shop)
