import pytest

from app.money import compute_order_amounts, resolve_commission_bps, split_refund

NAIRA = 100


def test_worked_example_no_discount_20_percent():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, commission_bps=2000)
    assert (a.buyer_total_kobo, a.commission_kobo, a.seller_amount_kobo) == (10_000 * NAIRA, 2_000 * NAIRA, 8_000 * NAIRA)


def test_worked_example_10_percent_seller_discount():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, seller_discount_kobo=1_000 * NAIRA, commission_bps=2000)
    assert (a.buyer_total_kobo, a.commission_kobo, a.seller_amount_kobo) == (9_000 * NAIRA, 1_800 * NAIRA, 7_200 * NAIRA)


def test_worked_example_discount_and_reduced_commission():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, seller_discount_kobo=1_000 * NAIRA, commission_bps=1000)
    assert (a.buyer_total_kobo, a.commission_kobo, a.seller_amount_kobo) == (9_000 * NAIRA, 900 * NAIRA, 8_100 * NAIRA)


def test_commission_not_charged_on_delivery_fee():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, delivery_fee_kobo=500 * NAIRA, commission_bps=2000)
    assert a.commission_kobo == 2_000 * NAIRA
    assert a.buyer_total_kobo == 10_500 * NAIRA
    assert a.seller_amount_kobo == 8_500 * NAIRA


def test_platform_funded_code_keeps_seller_payout_normal():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, platform_discount_kobo=1_000 * NAIRA, commission_bps=2000)
    assert a.buyer_total_kobo == 9_000 * NAIRA
    assert a.seller_amount_kobo == 8_000 * NAIRA
    assert a.platform_net_kobo == 1_000 * NAIRA


def test_provider_fee_absorbed_by_platform_by_default():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, commission_bps=2000, provider_fee_kobo=150 * NAIRA)
    assert a.seller_amount_kobo == 8_000 * NAIRA
    assert a.platform_net_kobo == 1_850 * NAIRA


def test_provider_fee_can_be_passed_to_seller():
    a = compute_order_amounts(
        unit_price_kobo=10_000 * NAIRA, commission_bps=2000, provider_fee_kobo=150 * NAIRA, provider_fee_absorbed=False
    )
    assert a.seller_amount_kobo == 7_850 * NAIRA
    assert a.platform_net_kobo == 2_000 * NAIRA


def test_rounding_is_floored_in_integer_kobo():
    a = compute_order_amounts(unit_price_kobo=333, commission_bps=2000)
    assert a.commission_kobo == 66
    assert a.commission_kobo + a.seller_amount_kobo == 333


@pytest.mark.parametrize("bad", [{"unit_price_kobo": -1}, {"commission_bps": 10_001}, {"seller_discount_kobo": 10_000 * NAIRA + 1}])
def test_invalid_amounts_rejected(bad):
    args = {"unit_price_kobo": 10_000 * NAIRA, "commission_bps": 2000, **bad}
    with pytest.raises(ValueError):
        compute_order_amounts(**args)


def test_commission_precedence_is_most_specific_first():
    assert resolve_commission_bps(default_bps=2000) == 2000
    assert resolve_commission_bps(default_bps=2000, category_bps=1500) == 1500
    assert resolve_commission_bps(default_bps=2000, category_bps=1500, plan_bps=1000) == 1000
    assert resolve_commission_bps(default_bps=2000, category_bps=1500, plan_bps=1000, seller_bps=500) == 500
    assert resolve_commission_bps(default_bps=2000, seller_bps=0) == 0


def test_full_refund_returns_all_commission():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, commission_bps=2000)
    r = split_refund(a, a.item_paid_kobo)
    assert (r.refund_to_buyer_kobo, r.commission_returned_kobo, r.seller_deduction_kobo) == (10_000 * NAIRA, 2_000 * NAIRA, 8_000 * NAIRA)


def test_partial_refund_reduces_commission_proportionally():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, commission_bps=2000)
    r = split_refund(a, 2_500 * NAIRA)
    assert (r.refund_to_buyer_kobo, r.commission_returned_kobo, r.seller_deduction_kobo) == (2_500 * NAIRA, 500 * NAIRA, 2_000 * NAIRA)


def test_refund_cannot_exceed_item_amount():
    a = compute_order_amounts(unit_price_kobo=10_000 * NAIRA, commission_bps=2000)
    with pytest.raises(ValueError):
        split_refund(a, a.item_paid_kobo + 1)
