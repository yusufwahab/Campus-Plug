"""Append-only money ledger. Every movement is a group of legs that sum to zero.

Accounts (balance = sum of legs; liabilities such as escrow show as negative):
  provider_clearing  cash sitting with the payment provider
  escrow             money held for buyers' orders (owed to sellers and to the platform)
  seller_payable     what we owe sellers once released
  platform_revenue   commission earned (negative = credit/earned)
  provider_fees      payment provider fees paid by the platform
  promo_cost         platform-funded campaign discounts
"""

import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.commerce import LedgerEntry, Order

PROVIDER_CLEARING = "provider_clearing"
ESCROW = "escrow"
SELLER_PAYABLE = "seller_payable"
PLATFORM_REVENUE = "platform_revenue"
PROVIDER_FEES = "provider_fees"
PROMO_COST = "promo_cost"


def post(db: Session, *, order: Order | None, kind: str, legs: list[tuple[str, int]], ref: str = "") -> str:
    """Records one balanced movement. Raises if the legs do not sum to zero, so an unbalanced entry can never be saved."""
    legs = [(account, amount) for account, amount in legs if amount != 0]
    if sum(amount for _, amount in legs) != 0:
        raise ValueError(f"Unbalanced ledger movement for {kind}")
    group = secrets.token_hex(8)
    for account, amount in legs:
        db.add(LedgerEntry(group_id=group, order_id=order.id if order else None, kind=kind, account=account, amount_kobo=amount, ref=ref))
    db.flush()
    return group


def balance(db: Session, account: str, order_id: int | None = None) -> int:
    query = select(func.coalesce(func.sum(LedgerEntry.amount_kobo), 0)).where(LedgerEntry.account == account)
    if order_id is not None:
        query = query.where(LedgerEntry.order_id == order_id)
    return int(db.scalar(query) or 0)
