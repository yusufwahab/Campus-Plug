"""Money rules. Pure functions, integer kobo only, rates in basis points (20% = 2000).

Commission is charged on what the buyer pays for the ITEM after seller discounts. Never on delivery fees.
Platform-funded campaign discounts reduce what the buyer pays but not the seller's payout.
"""

from dataclasses import dataclass

BPS = 10_000


@dataclass(frozen=True)
class OrderAmounts:
    unit_price_kobo: int
    quantity: int
    seller_discount_kobo: int
    platform_discount_kobo: int
    item_paid_kobo: int  # commission base: item price after seller discount (before platform-funded discount)
    delivery_fee_kobo: int
    buyer_total_kobo: int
    commission_bps: int
    commission_kobo: int
    seller_amount_kobo: int  # item_paid - commission + delivery fee
    provider_fee_kobo: int
    platform_net_kobo: int  # commission - platform-funded discount - provider fee (if the platform absorbs it)


def commission_for(item_paid_kobo: int, commission_bps: int) -> int:
    return item_paid_kobo * commission_bps // BPS


def resolve_commission_bps(
    *, default_bps: int, category_bps: int | None = None, plan_bps: int | None = None, seller_bps: int | None = None
) -> int:
    """Most specific rule wins: seller override, then plan, then category, then the platform default."""
    for candidate in (seller_bps, plan_bps, category_bps):
        if candidate is not None:
            return candidate
    return default_bps


def compute_order_amounts(
    *,
    unit_price_kobo: int,
    quantity: int = 1,
    seller_discount_kobo: int = 0,
    platform_discount_kobo: int = 0,
    delivery_fee_kobo: int = 0,
    commission_bps: int,
    provider_fee_kobo: int = 0,
    provider_fee_absorbed: bool = True,
) -> OrderAmounts:
    if (
        min(unit_price_kobo, quantity, seller_discount_kobo, platform_discount_kobo, delivery_fee_kobo, commission_bps, provider_fee_kobo)
        < 0
    ):
        raise ValueError("Amounts cannot be negative")
    if not 0 <= commission_bps <= BPS:
        raise ValueError("Commission rate out of range")
    gross = unit_price_kobo * quantity
    if seller_discount_kobo > gross:
        raise ValueError("Discount cannot exceed the item price")
    item_paid = gross - seller_discount_kobo
    if platform_discount_kobo > item_paid:
        raise ValueError("Discount cannot exceed the item price")
    commission = commission_for(item_paid, commission_bps)
    buyer_total = item_paid - platform_discount_kobo + delivery_fee_kobo
    seller_amount = item_paid - commission + delivery_fee_kobo
    platform_net = commission - platform_discount_kobo - (provider_fee_kobo if provider_fee_absorbed else 0)
    if not provider_fee_absorbed:
        # The seller bears the provider fee instead of the platform.
        seller_amount -= provider_fee_kobo
    return OrderAmounts(
        unit_price_kobo=unit_price_kobo,
        quantity=quantity,
        seller_discount_kobo=seller_discount_kobo,
        platform_discount_kobo=platform_discount_kobo,
        item_paid_kobo=item_paid,
        delivery_fee_kobo=delivery_fee_kobo,
        buyer_total_kobo=buyer_total,
        commission_bps=commission_bps,
        commission_kobo=commission,
        seller_amount_kobo=seller_amount,
        provider_fee_kobo=provider_fee_kobo,
        platform_net_kobo=platform_net,
    )


@dataclass(frozen=True)
class RefundSplit:
    refund_to_buyer_kobo: int
    commission_returned_kobo: int
    seller_deduction_kobo: int


def split_refund(amounts: OrderAmounts, refund_item_kobo: int, *, include_delivery: bool = False) -> RefundSplit:
    """A full refund returns all commission; a partial refund returns it proportionally."""
    if not 0 < refund_item_kobo <= amounts.item_paid_kobo:
        raise ValueError("Refund must be between 1 kobo and the item amount")
    if refund_item_kobo == amounts.item_paid_kobo:
        commission_back = amounts.commission_kobo
    else:
        commission_back = amounts.commission_kobo * refund_item_kobo // amounts.item_paid_kobo
    delivery = amounts.delivery_fee_kobo if include_delivery else 0
    return RefundSplit(
        refund_to_buyer_kobo=refund_item_kobo + delivery,
        commission_returned_kobo=commission_back,
        seller_deduction_kobo=refund_item_kobo - commission_back + delivery,
    )
