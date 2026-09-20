import pytest

from app.services.pricing import calculate_sale_item, from_cents, to_cents


def test_to_cents_and_back():
    assert to_cents("19.90") == 1990
    assert from_cents(1990) == 19.90


def test_calculate_sale_item_basic():
    calc = calculate_sale_item(
        quantity=2,
        unit_price_cents=2000,  # R$20,00
        unit_cost_cents=800,  # R$8,00
        platform_fee_pct=0.10,  # 10%
        fixed_fee_cents=100,  # R$1,00
        shipping_cost_cents=500,  # R$5,00
        other_fee_pct=0.02,  # 2%
    )

    assert calc.gross_total_cents == 4000
    # platform fee: 4000 * 0.10 + 100 = 500 ; other fee: 4000 * 0.02 = 80
    # total fees = 500 + 80 + 500 (shipping) = 1080
    assert calc.total_fees_cents == 1080
    # product cost = 800 * 2 = 1600 ; total cost = 1600 + 1080 = 2680
    assert calc.total_cost_cents == 2680
    assert calc.net_profit_cents == 4000 - 2680


def test_calculate_sale_item_rejects_non_positive_quantity():
    with pytest.raises(ValueError):
        calculate_sale_item(
            quantity=0,
            unit_price_cents=1000,
            unit_cost_cents=500,
        )
