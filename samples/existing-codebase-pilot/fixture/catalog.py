"""Existing catalog pricing behavior before the pilot change."""

from decimal import Decimal

PRICES = {"adapter": Decimal("12.50"), "cable": Decimal("4.00")}


def quote(sku: str, quantity: int) -> Decimal:
    return PRICES[sku] * quantity
