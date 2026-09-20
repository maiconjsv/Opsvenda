"""Core margin/fee math.

Used both by the manual sale form and the CSV import, so the formula lives in
exactly one place. Every value returned here is meant to be stored as a
snapshot on the SaleItem row - it must never be recomputed later from the
Product's current price or the MarginProfile's current settings.
"""

from dataclasses import dataclass


def to_cents(value) -> int:
    """Convert a reais amount (str/float/int, e.g. '19.90') to integer cents."""
    return round(float(value) * 100)


def from_cents(cents: int) -> float:
    return cents / 100


@dataclass(frozen=True)
class SaleItemCalculation:
    quantity: int
    unit_price_cents: int
    unit_cost_cents: int
    platform_fee_pct: float
    fixed_fee_cents: int
    shipping_cost_cents: int
    other_fee_pct: float

    gross_total_cents: int
    total_fees_cents: int
    total_cost_cents: int
    net_profit_cents: int


def calculate_sale_item(
    *,
    quantity: int,
    unit_price_cents: int,
    unit_cost_cents: int,
    platform_fee_pct: float = 0.0,
    fixed_fee_cents: int = 0,
    shipping_cost_cents: int = 0,
    other_fee_pct: float = 0.0,
) -> SaleItemCalculation:
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    gross_total_cents = unit_price_cents * quantity

    platform_fee_cents = round(gross_total_cents * platform_fee_pct) + fixed_fee_cents
    other_fee_cents = round(gross_total_cents * other_fee_pct)
    total_fees_cents = platform_fee_cents + other_fee_cents + shipping_cost_cents

    product_cost_cents = unit_cost_cents * quantity
    total_cost_cents = product_cost_cents + total_fees_cents

    net_profit_cents = gross_total_cents - total_cost_cents

    return SaleItemCalculation(
        quantity=quantity,
        unit_price_cents=unit_price_cents,
        unit_cost_cents=unit_cost_cents,
        platform_fee_pct=platform_fee_pct,
        fixed_fee_cents=fixed_fee_cents,
        shipping_cost_cents=shipping_cost_cents,
        other_fee_pct=other_fee_pct,
        gross_total_cents=gross_total_cents,
        total_fees_cents=total_fees_cents,
        total_cost_cents=total_cost_cents,
        net_profit_cents=net_profit_cents,
    )
