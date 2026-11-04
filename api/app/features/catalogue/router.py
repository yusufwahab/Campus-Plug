from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.deps import DB
from app.models.catalogue import Category
from app.models.identity import Campus, Location

router = APIRouter(tags=["catalogue"])


class CampusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campus_id: int
    name: str
    kind: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    tint: str


@router.get("/campuses", response_model=list[CampusOut])
def campuses(db: DB) -> list[Campus]:
    return list(db.scalars(select(Campus).where(Campus.enabled.is_(True)).order_by(Campus.name)))


@router.get("/locations", response_model=list[LocationOut])
def locations(db: DB, campus_id: int | None = None) -> list[Location]:
    query = select(Location).join(Campus).where(Campus.enabled.is_(True), Location.enabled.is_(True)).order_by(Location.id)
    if campus_id:
        query = query.where(Location.campus_id == campus_id)
    return list(db.scalars(query))


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: DB) -> list[Category]:
    return list(db.scalars(select(Category).where(Category.enabled.is_(True)).order_by(Category.position)))
