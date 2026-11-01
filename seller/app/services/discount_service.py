from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.product_service import get_product

CENT = Decimal("0.01")


def quote_discount(original_price: Decimal, percent: Decimal) -> Decimal:
    """Calculate a price from the catalog price; never mutate Product.price."""
    discount = (original_price * percent / Decimal("100"))
    return (original_price - discount).quantize(CENT, rounding=ROUND_HALF_UP)


async def apply_discount(
    db: AsyncSession,
    product_id: UUID,
    percent: float | None = None,
    target_price: float | None = None,
    best_price: bool = False,
    expected_original_price: float | None = None,
) -> dict:
    product = await get_product(db, product_id)
    if product is None:
        return {
            "product_id": str(product_id), "original_price": None,
            "requested_discount_percent": percent, "applied_discount_percent": 0,
            "discounted_price": None, "applied": False,
            "rejection_reason": "Product not found.",
            "maximum_discount_percent": float(settings.max_discount_percent),
            "best_allowed_offer": None,
        }

    original = Decimal(product.price).quantize(CENT)
    maximum = Decimal(str(settings.max_discount_percent))
    try:
        expected_matches = expected_original_price is None or Decimal(str(expected_original_price)).quantize(CENT) == original
    except (InvalidOperation, ValueError, TypeError):
        expected_matches = False
    if not expected_matches:
        return {
            "product_id": str(product.id), "original_price": float(original),
            "requested_discount_percent": percent, "applied_discount_percent": 0.0,
            "discounted_price": float(original), "applied": False,
            "rejection_reason": "Catalog price changed since this offer was made. Please request a fresh offer.",
            "maximum_discount_percent": float(maximum), "best_allowed_offer": None,
            "expected_original_price_matches": False,
        }
    mode_count = int(percent is not None) + int(target_price is not None) + int(best_price)
    requested_percent: Decimal | None = None
    if mode_count != 1:
        reason = "Specify exactly one of percent, target_price, or best_price."
    elif best_price:
        requested_percent = maximum
        reason = None
    elif target_price is not None:
        try:
            target = Decimal(str(target_price))
            if not target.is_finite() or target < 0:
                raise InvalidOperation
            requested_percent = ((original - target) / original * Decimal("100"))
            reason = None
        except (InvalidOperation, ZeroDivisionError):
            reason = "Target price must be a valid non-negative amount."
    else:
        try:
            if percent is None or not isfinite(float(percent)):
                raise InvalidOperation
            requested_percent = Decimal(str(percent))
            reason = None
        except (InvalidOperation, TypeError, ValueError):
            reason = "Discount percent must be a finite number."

    if reason is None and requested_percent is not None:
        if requested_percent < 0:
            reason = "Target price is above the catalog price; a negative discount is not valid."
        elif requested_percent > maximum:
            reason = f"Requested discount exceeds the seller maximum of {maximum:.2f}%."

    best_offer = {
        "discount_percent": float(maximum),
        "discounted_price": float(quote_discount(original, maximum)),
    }
    if reason:
        return {
            "product_id": str(product.id),
            "original_price": float(original),
            "requested_discount_percent": float(requested_percent) if requested_percent is not None else percent,
            "applied_discount_percent": 0.0,
            "discounted_price": float(original),
            "applied": False,
            "rejection_reason": reason,
            "maximum_discount_percent": float(maximum),
            "best_allowed_offer": best_offer if requested_percent is not None and requested_percent > maximum else None,
            "expected_original_price_matches": expected_matches,
        }

    assert requested_percent is not None
    applied_percent = requested_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    final_price = quote_discount(original, applied_percent)
    return {
        "product_id": str(product.id),
        "original_price": float(original),
        "requested_discount_percent": float(requested_percent),
        "applied_discount_percent": float(applied_percent),
        "discounted_price": float(final_price),
        "applied": True,
        "rejection_reason": None,
        "maximum_discount_percent": float(maximum),
        "best_allowed_offer": None,
        "expected_original_price_matches": True,
    }
