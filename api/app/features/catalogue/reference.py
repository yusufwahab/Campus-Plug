"""Reference data: campuses, locations and categories. Needed in every environment (including production)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import Category
from app.models.identity import Campus, Location

UNILAG_LOCATIONS = [
    ("Madam Tinubu Hall (MTH)", "hall"),
    ("Makama Bida", "hall"),
    ("Fagunwa", "hall"),
    ("Eni-Njoku", "hall"),
    ("Sodehinde", "hall"),
    ("Femi Gbajabiamila", "hall"),
    ("El-Kanemi", "hall"),
    ("Saburi Biobaku", "hall"),
    ("Kofo Ademola", "hall"),
    ("Queen Amina", "hall"),
    ("Honours", "hall"),
    ("UNILAG Women Society (ULWS) Female Hostel", "hall"),
    ("King Jaja", "hall"),
    ("Mariere", "hall"),
    ("Queen Moremi", "hall"),
    ("On Campus", "area"),
    ("Off Campus", "area"),
]

CATEGORIES = [
    ("food", "Food", "peach"),
    ("fashion", "Fashion", "lilac"),
    ("beauty", "Beauty", "butter"),
    ("gadgets", "Gadgets", "sky"),
    ("services", "Services", "mint"),
    ("accessories", "Accessories", "peach"),
    ("academic", "Academic", "sky"),
    ("others", "Others", "lilac"),
]


def seed_reference(db: Session) -> None:
    """Idempotent: safe to run on every deploy. Admin edits are never overwritten."""
    campus = db.scalar(select(Campus).where(Campus.slug == "unilag"))
    if campus is None:
        campus = Campus(slug="unilag", name="University of Lagos (UNILAG)", enabled=True)
        db.add(campus)
        db.flush()
        for name, kind in UNILAG_LOCATIONS:
            db.add(Location(campus_id=campus.id, name=name, kind=kind))
    if db.scalar(select(Category.id).limit(1)) is None:
        for position, (slug, name, tint) in enumerate(CATEGORIES):
            db.add(Category(slug=slug, name=name, tint=tint, position=position))
    db.commit()
