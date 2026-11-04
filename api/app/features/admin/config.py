from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.audit import log_admin_action
from app.deps import DB, AdminUser
from app.models.catalogue import Category
from app.models.identity import Campus, Location
from app.models.system import Setting
from app.models.trust import Announcement, BannedItem, Policy
from app.settings_store import DEFAULTS, all_settings

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- settings: every business rule an Admin can change without code ----------------------------------------------


class SettingsOut(BaseModel):
    values: dict[str, Any]


class SettingIn(BaseModel):
    value: Any
    reason: str = Field(min_length=3)


@router.get("/settings", response_model=SettingsOut)
def get_settings_all(admin: AdminUser, db: DB) -> SettingsOut:
    return SettingsOut(values=all_settings(db))


def _coerce(key: str, value: Any) -> Any:
    """Settings keep the type of their default: ints stay ints, flags stay flags, lists stay lists."""
    default = DEFAULTS[key]
    if isinstance(default, bool) and not isinstance(value, bool):
        raise HTTPException(422, f"{key} must be true or false")
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HTTPException(422, f"{key} must be a whole number of zero or more")
        if key == "commission_bps" and value > 10_000:
            raise HTTPException(422, "Commission cannot exceed 100%")
    if isinstance(default, list) and (not isinstance(value, list) or not all(isinstance(v, str) for v in value)):
        raise HTTPException(422, f"{key} must be a list of text values")
    return value


@router.put("/settings/{key}", response_model=SettingsOut)
def set_setting(key: str, body: SettingIn, admin: AdminUser, db: DB) -> SettingsOut:
    """Changes apply to new orders only: orders store their own commission rate and fee handling when created."""
    if key not in DEFAULTS:
        raise HTTPException(404, "Unknown setting")
    value = _coerce(key, body.value)
    current = all_settings(db)[key]
    log_admin_action(db, admin, "setting.changed", "setting", key, reason=body.reason, before=current, after=value)
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()
    return SettingsOut(values=all_settings(db))


# ---- categories --------------------------------------------------------------------------------------------------


class CategoryIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{2,40}$")
    name: str = Field(min_length=2, max_length=80)
    tint: str = Field(pattern=r"^(peach|lilac|sky|butter|mint)$")
    enabled: bool = True
    requires_verification: bool = False
    commission_override_bps: int | None = Field(default=None, ge=0, le=10_000)
    reason: str = Field(min_length=3)


class CategoryAdmin(BaseModel):
    id: int
    slug: str
    name: str
    tint: str
    enabled: bool
    requires_verification: bool
    commission_override_bps: int | None


def _cat(c: Category) -> CategoryAdmin:
    return CategoryAdmin(
        id=c.id,
        slug=c.slug,
        name=c.name,
        tint=c.tint,
        enabled=c.enabled,
        requires_verification=c.requires_verification,
        commission_override_bps=c.commission_override_bps,
    )


@router.get("/categories", response_model=list[CategoryAdmin])
def list_categories(admin: AdminUser, db: DB) -> list[CategoryAdmin]:
    return [_cat(c) for c in db.scalars(select(Category).order_by(Category.position, Category.id))]


@router.post("/categories", response_model=CategoryAdmin, status_code=201)
def create_category(body: CategoryIn, admin: AdminUser, db: DB) -> CategoryAdmin:
    if db.scalar(select(Category.id).where(Category.slug == body.slug)):
        raise HTTPException(409, "That slug is already used.")
    count = len(db.scalars(select(Category.id)).all())
    cat = Category(**body.model_dump(exclude={"reason"}), position=count)
    db.add(cat)
    log_admin_action(db, admin, "category.created", "category", body.slug, reason=body.reason, after=body.model_dump(exclude={"reason"}))
    db.commit()
    return _cat(cat)


@router.put("/categories/{category_id}", response_model=CategoryAdmin)
def update_category(category_id: int, body: CategoryIn, admin: AdminUser, db: DB) -> CategoryAdmin:
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(404, "Category not found")
    clash = db.scalar(select(Category.id).where(Category.slug == body.slug, Category.id != cat.id))
    if clash:
        raise HTTPException(409, "That slug is already used.")
    log_admin_action(
        db,
        admin,
        "category.updated",
        "category",
        cat.slug,
        reason=body.reason,
        before=_cat(cat).model_dump(),
        after=body.model_dump(exclude={"reason"}),
    )
    for k, v in body.model_dump(exclude={"reason"}).items():
        setattr(cat, k, v)
    db.commit()
    return _cat(cat)


# ---- campuses and locations --------------------------------------------------------------------------------------


class CampusIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{2,40}$")
    name: str = Field(min_length=2, max_length=120)
    enabled: bool
    reason: str = Field(min_length=3)


class CampusAdmin(BaseModel):
    id: int
    slug: str
    name: str
    enabled: bool


class LocationIn(BaseModel):
    campus_id: int
    name: str = Field(min_length=2, max_length=120)
    kind: str = Field(pattern=r"^(hall|area)$")
    enabled: bool = True
    reason: str = Field(min_length=3)


class LocationAdmin(BaseModel):
    id: int
    campus_id: int
    name: str
    kind: str
    enabled: bool


@router.get("/campuses", response_model=list[CampusAdmin])
def list_campuses(admin: AdminUser, db: DB) -> list[Campus]:
    return list(db.scalars(select(Campus).order_by(Campus.id)))


@router.post("/campuses", response_model=CampusAdmin, status_code=201)
def create_campus(body: CampusIn, admin: AdminUser, db: DB) -> Campus:
    if db.scalar(select(Campus.id).where(Campus.slug == body.slug)):
        raise HTTPException(409, "That slug is already used.")
    campus = Campus(slug=body.slug, name=body.name, enabled=body.enabled)
    db.add(campus)
    log_admin_action(db, admin, "campus.created", "campus", body.slug, reason=body.reason, after=body.model_dump(exclude={"reason"}))
    db.commit()
    return campus


@router.put("/campuses/{campus_id}", response_model=CampusAdmin)
def update_campus(campus_id: int, body: CampusIn, admin: AdminUser, db: DB) -> Campus:
    campus = db.get(Campus, campus_id)
    if campus is None:
        raise HTTPException(404, "Campus not found")
    log_admin_action(
        db,
        admin,
        "campus.updated",
        "campus",
        campus.slug,
        reason=body.reason,
        before={"name": campus.name, "enabled": campus.enabled},
        after={"name": body.name, "enabled": body.enabled},
    )
    campus.name, campus.enabled = body.name, body.enabled
    db.commit()
    return campus


@router.get("/locations", response_model=list[LocationAdmin])
def list_locations(admin: AdminUser, db: DB, campus_id: int | None = None) -> list[Location]:
    query = select(Location).order_by(Location.id)
    if campus_id:
        query = query.where(Location.campus_id == campus_id)
    return list(db.scalars(query))


@router.post("/locations", response_model=LocationAdmin, status_code=201)
def create_location(body: LocationIn, admin: AdminUser, db: DB) -> Location:
    if db.get(Campus, body.campus_id) is None:
        raise HTTPException(422, "Unknown campus")
    loc = Location(campus_id=body.campus_id, name=body.name, kind=body.kind, enabled=body.enabled)
    db.add(loc)
    log_admin_action(db, admin, "location.created", "location", body.name, reason=body.reason, after=body.model_dump(exclude={"reason"}))
    db.commit()
    return loc


@router.put("/locations/{location_id}", response_model=LocationAdmin)
def update_location(location_id: int, body: LocationIn, admin: AdminUser, db: DB) -> Location:
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "Location not found")
    log_admin_action(
        db,
        admin,
        "location.updated",
        "location",
        loc.id,
        reason=body.reason,
        before={"name": loc.name, "enabled": loc.enabled},
        after={"name": body.name, "enabled": body.enabled},
    )
    loc.name, loc.kind, loc.enabled = body.name, body.kind, body.enabled
    db.commit()
    return loc


# ---- banned items, announcements, policy text --------------------------------------------------------------------


class BannedIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    reason: str = Field(default="", max_length=300)
    extra_review: bool = False


class BannedOut(BannedIn):
    id: int


@router.post("/banned-items", response_model=BannedOut, status_code=201)
def add_banned(body: BannedIn, admin: AdminUser, db: DB) -> BannedItem:
    if db.scalar(select(BannedItem.id).where(BannedItem.name == body.name)):
        raise HTTPException(409, "Already on the list.")
    item = BannedItem(**body.model_dump())
    db.add(item)
    log_admin_action(db, admin, "banned_item.added", "banned_item", body.name, reason=body.reason or "Added to banned items list")
    db.commit()
    return item


@router.delete("/banned-items/{item_id}", status_code=204)
def remove_banned(item_id: int, reason: str, admin: AdminUser, db: DB) -> None:
    item = db.get(BannedItem, item_id)
    if item is None:
        raise HTTPException(404, "Not found")
    log_admin_action(db, admin, "banned_item.removed", "banned_item", item.name, reason=reason)
    db.delete(item)
    db.commit()


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    body: str = Field(min_length=3, max_length=2000)
    audience: str = Field(default="all", pattern=r"^(all|sellers|buyers)$")


class AnnouncementOut(AnnouncementIn):
    id: int
    active: bool


@router.get("/announcements", response_model=list[AnnouncementOut])
def list_announcements(admin: AdminUser, db: DB) -> list[Announcement]:
    return list(db.scalars(select(Announcement).order_by(Announcement.id.desc())))


@router.post("/announcements", response_model=AnnouncementOut, status_code=201)
def create_announcement(body: AnnouncementIn, admin: AdminUser, db: DB) -> Announcement:
    item = Announcement(**body.model_dump(), created_by=admin.id)
    db.add(item)
    log_admin_action(db, admin, "announcement.created", "announcement", body.title, reason="Published announcement")
    db.commit()
    return item


@router.post("/announcements/{announcement_id}/active", response_model=AnnouncementOut)
def set_announcement_active(announcement_id: int, active: bool, admin: AdminUser, db: DB) -> Announcement:
    item = db.get(Announcement, announcement_id)
    if item is None:
        raise HTTPException(404, "Not found")
    log_admin_action(
        db, admin, "announcement.shown" if active else "announcement.hidden", "announcement", item.title, reason="Visibility changed"
    )
    item.active = active
    db.commit()
    return item


class PolicyIn(BaseModel):
    body: str = Field(min_length=20)
    reason: str = Field(min_length=3)


@router.put("/policies/{slug}", status_code=204)
def set_policy(slug: str, body: PolicyIn, admin: AdminUser, db: DB) -> None:
    if slug not in ("terms", "privacy", "seller-rules"):
        raise HTTPException(404, "Unknown policy")
    row = db.get(Policy, slug)
    log_admin_action(
        db,
        admin,
        "policy.updated",
        "policy",
        slug,
        reason=body.reason,
        before={"chars": len(row.body) if row else 0},
        after={"chars": len(body.body)},
    )
    if row is None:
        db.add(Policy(slug=slug, body=body.body))
    else:
        row.body = body.body
    db.commit()
