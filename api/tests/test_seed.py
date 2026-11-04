import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models.catalogue import Category, Listing
from app.seed_dev import seed_dev


def test_dev_seed_covers_all_categories_and_is_idempotent(db):
    seed_dev(db)
    seed_dev(db)
    covered = {c for (c,) in db.execute(select(Category.slug).join(Listing, Listing.category_id == Category.id)).all()}
    assert covered == {"food", "fashion", "beauty", "gadgets", "services", "accessories", "academic", "others"}
    assert db.scalar(select(Listing.id).where(Listing.public_id.like("CP-P-%")))


def test_dev_seed_refuses_production(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            seed_dev(db)
    finally:
        monkeypatch.setenv("APP_ENV", "test")
        get_settings.cache_clear()
