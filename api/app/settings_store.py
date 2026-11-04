from typing import Any

from sqlalchemy.orm import Session

from app.models.system import Setting

# Every value an Admin can change without code. Money in kobo, rates in basis points, windows in hours.
DEFAULTS: dict[str, Any] = {
    "commission_bps": 2000,
    "provider_fee_absorbed": True,
    "instant_split": False,
    "unverified_listing_limit": 3,
    "high_value_threshold_kobo": 5_000_000,
    "verification_required_categories": [],
    "free_listing_days": 30,
    "renewal_days": 30,
    "max_images_per_listing": 6,
    "seller_accept_hours": 2,
    "buyer_confirm_hours": 48,
    "dispute_response_hours": 48,
    "service_cancel_hours": 24,
    "pending_payment_hours": 24,
    "trusted_min_confirmed_deals": 10,
    "trusted_min_rating_x10": 45,
    "allow_vendors": False,
    "sms_enabled": False,
    "whatsapp_enabled": False,
    "listing_price_spike_pct": 50,
}


def get_setting(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    return row.value if row else DEFAULTS[key]


def all_settings(db: Session) -> dict[str, Any]:
    stored = {s.key: s.value for s in db.query(Setting).all()}
    return {**DEFAULTS, **stored}
