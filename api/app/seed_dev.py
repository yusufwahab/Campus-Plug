"""FAKE data for local and staging only. Refuses to run in production. See docs/SEED_ACCOUNTS.md."""

import os
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.features.catalogue.reference import seed_reference
from app.ids import next_public_id
from app.models.catalogue import Category, Listing, Shop
from app.models.identity import Campus, Location, User, UserPermission
from app.security import hash_password

PASSWORD = "Passw0rd!test"  # test accounts only
ADMIN_TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # test admin only; real admins enrol their own authenticator

ACCOUNTS = [
    # email, name, role, extra
    ("admin1@example.com", "Ada Admin", "admin", {"mfa_secret": ADMIN_TOTP_SECRET, "mfa_enabled": True}),
    ("admin2@example.com", "Bola Admin", "admin", {"mfa_secret": ADMIN_TOTP_SECRET, "mfa_enabled": True}),
    ("verifier@example.com", "Vera Verifier", "buyer", {}),
    ("rep@example.com", "Rita Rep", "buyer", {}),
    ("buyer1@example.com", "Tolu Buyer", "buyer", {}),
    ("buyer2@example.com", "Chidi Buyer", "buyer", {}),
    ("seller.verified@example.com", "Kemi Verified Seller", "seller", {}),
    ("seller.new@example.com", "Femi Unverified Seller", "seller", {}),
]


# slug, type, title, description, price (naira), condition, location name prefix
LISTINGS = [
    ("food", "product", "Jollof rice and chicken", "Party jollof with fried chicken. Ready daily from noon.", 2500, "new", "Madam Tinubu"),
    ("food", "product", "Meat pie box (6)", "Soft pastry, rich filling. Pre-order by 9am.", 3000, "new", "Fagunwa"),
    ("fashion", "product", "Thrifted denim jacket", "Size M, barely worn. Pickup at the hall.", 8500, "like_new", "Makama"),
    ("fashion", "product", "Ankara tote bag", "Handmade, fits a 15 inch laptop.", 6000, "new", "Madam Tinubu"),
    (
        "beauty",
        "service",
        "Hair braiding",
        "Box braids and cornrows. Bring your own extensions or buy from me.",
        12000,
        None,
        "Queen Amina",
    ),
    ("beauty", "product", "Shea butter body cream", "Unscented, 250ml jar.", 3500, "new", "Kofo"),
    ("gadgets", "product", "Used Redmi Note 11", "128GB, battery health good, comes with charger.", 95000, "used", "Eni-Njoku"),
    ("gadgets", "product", "Power bank 20000mAh", "Fast charging, two ports.", 14000, "new", "Sodehinde"),
    ("services", "service", "Laundry and ironing", "Weekly pickup and drop-off at your hall.", 4000, None, "El-Kanemi"),
    ("services", "service", "Logo and flyer design", "Two revisions included. Delivered in 48 hours.", 10000, None, "On Campus"),
    ("accessories", "product", "Beaded bracelet set", "Set of 5, custom colours on request.", 2000, "new", "Honours"),
    ("accessories", "product", "Laptop sleeve 14 inch", "Water resistant, padded.", 5500, "new", "Saburi"),
    ("academic", "service", "Maths and Physics tutoring", "100 and 200 level. One hour sessions on campus.", 3000, None, "On Campus"),
    ("academic", "product", "Engineering Mathematics textbook", "Good condition, no torn pages.", 7000, "used", "Mariere"),
    ("others", "product", "Study desk lamp", "Rechargeable, three brightness levels.", 6500, "new", "King Jaja"),
    ("others", "product", "Mini fan", "USB powered, quiet.", 4500, "new", "Queen Moremi"),
]


def seed_marketplace(db: Session) -> None:
    campus = db.scalar(select(Campus).where(Campus.slug == "unilag"))
    if campus is None or db.scalar(select(Shop.id).limit(1)) is not None:
        return
    shops: list[Shop] = []
    for email, name, slug, verified in (
        ("seller.verified@example.com", "Kemi's Corner", "kemis-corner", True),
        ("seller.new@example.com", "Femi Fresh Finds", "femi-fresh-finds", False),
    ):
        owner = db.scalar(select(User).where(User.email == email))
        if owner is None:
            raise RuntimeError("Seed accounts missing")
        shop = Shop(
            public_id=next_public_id(db, "SL"),
            user_id=owner.id,
            slug=slug,
            name=name,
            bio="Fake demo shop for local testing.",
            campus_id=campus.id,
            rules_accepted_at=utcnow(),
            verification_status="verified" if verified else "unverified",
            trust_level="trusted_seller" if verified else "email_confirmed",
            confirmed_deals=12 if verified else 0,
            rating_sum=47 if verified else 0,
            rating_count=10 if verified else 0,
            payout_bank="GTBank" if verified else None,
            payout_account_number="0123456789" if verified else None,  # fake test account
            payout_account_name=name if verified else None,
        )
        db.add(shop)
        shops.append(shop)
    db.flush()
    for i, (cat, kind, title, desc, naira, condition, place) in enumerate(LISTINGS):
        category = db.scalar(select(Category).where(Category.slug == cat))
        location = db.scalar(select(Location).where(Location.name.like(f"{place}%")))
        shop = shops[0] if i % 4 else shops[1]
        db.add(
            Listing(
                public_id=next_public_id(db, "P" if kind == "product" else "S"),
                shop_id=shop.id,
                type=kind,
                category_id=category.id,  # type: ignore[union-attr]
                title=title,
                description=desc,
                price_kobo=naira * 100,
                negotiable=naira > 5000,
                campus_id=campus.id,
                location_id=location.id if location else None,
                status="active",
                condition=condition,
                quantity=50,  # plenty, so many demo orders and end-to-end journeys do not sell the item out
                fulfilment="both" if kind == "product" else "pickup",
                delivery_fee_kobo=50000 if kind == "product" else 0,
                expires_at=utcnow() + timedelta(days=30),
                views=(i * 7) % 40,
            )
        )
    db.commit()


def seed_dev(db: Session) -> None:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("seed_dev must never run in production")
    if not settings.database_url.startswith("sqlite") and os.environ.get("ALLOW_DEV_SEED") != "1":
        # Fake accounts with a known password must never land in a real PostgreSQL database by accident (for example
        # a staging rehearsal that points at your real database). Opt in on purpose with ALLOW_DEV_SEED=1.
        raise RuntimeError("seed_dev only runs on SQLite. Set ALLOW_DEV_SEED=1 to seed a throw-away PostgreSQL database.")
    seed_reference(db)
    mth = db.scalar(select(Location).where(Location.name.like("Madam Tinubu%")))
    for email, name, role, extra in ACCOUNTS:
        if db.scalar(select(User).where(User.email == email)):
            continue
        db.add(
            User(
                email=email, full_name=name, role=role, password_hash=hash_password(PASSWORD), email_verified=True, onboarded=True, **extra
            )
        )
    db.flush()
    verifier = db.scalar(select(User).where(User.email == "verifier@example.com"))
    rep = db.scalar(select(User).where(User.email == "rep@example.com"))
    if not (verifier and rep and mth):
        raise RuntimeError("Reference data missing; seed_reference failed")
    for user, perm, loc in ((verifier, "verifier", None), (rep, "hall_rep", mth.id)):
        if not db.scalar(select(UserPermission).where(UserPermission.user_id == user.id, UserPermission.permission == perm)):
            db.add(UserPermission(user_id=user.id, permission=perm, hall_location_id=loc))
    db.commit()
    seed_marketplace(db)


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as session:
        seed_dev(session)
    print("Dev seed complete (fake data).")
