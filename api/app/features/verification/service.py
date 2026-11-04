from sqlalchemy.orm import Session

from app.models.catalogue import Shop
from app.settings_store import get_setting


def recompute_trust(db: Session, shop: Shop) -> str:
    """Email Confirmed -> Verified Student -> Trusted Seller.

    Trusted Seller is earned automatically from confirmed deals and good ratings, using Admin-set thresholds.
    """
    if shop.verification_status != "verified":
        shop.trust_level = "email_confirmed"
        return shop.trust_level
    shop.trust_level = "verified_student"
    average_x10 = shop.rating_sum * 10 // shop.rating_count if shop.rating_count else 0
    if shop.confirmed_deals >= get_setting(db, "trusted_min_confirmed_deals") and average_x10 >= get_setting(db, "trusted_min_rating_x10"):
        shop.trust_level = "trusted_seller"
    return shop.trust_level
