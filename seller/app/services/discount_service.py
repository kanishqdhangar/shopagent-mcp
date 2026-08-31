from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.product_service import get_product


async def apply_discount(
    db: AsyncSession,
    product_id: UUID,
    percent: float,
) -> dict:
    if percent < 0:
        return {
            "applied": False,
            "reason": "Discount percent cannot be negative.",
        }

    if percent > settings.max_discount_percent:
        return {
            "applied": False,
            "reason": (
                f"Discount of {percent:.2f}% exceeds the maximum "
                f"allowed discount of "
                f"{settings.max_discount_percent:.2f}%."
            ),
        }

    product = await get_product(
        db,
        product_id,
    )

    if product is None:
        return {
            "applied": False,
            "reason": "Product not found.",
        }

    original_price = Decimal(product.price)

    discount_amount = (
        original_price * Decimal(str(percent)) / Decimal("100")
    )

    discounted_price = (
        original_price - discount_amount
    ).quantize(Decimal("0.01"))

    return {
        "applied": True,
        "product_id": str(product.id),
        "original_price": float(original_price),
        "discount_percent": percent,
        "discounted_price": float(discounted_price),
    }