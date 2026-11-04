from sqlalchemy.orm import Session

from app.models.growth import AnalyticsEvent


def record(
    db: Session,
    kind: str,
    *,
    campus_id: int | None = None,
    shop_id: int | None = None,
    listing_id: int | None = None,
    user_id: int | None = None,
) -> None:
    """Adds one analytics event. The caller commits."""
    db.add(AnalyticsEvent(kind=kind, campus_id=campus_id, shop_id=shop_id, listing_id=listing_id, user_id=user_id))
