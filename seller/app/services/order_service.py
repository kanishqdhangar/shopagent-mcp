import razorpay

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Order, Product


async def create_order(
    db: AsyncSession,
    items: list[dict],
) -> dict:
    if not items:
        return {
            "created": False,
            "reason": "Cart is empty.",
        }

    validated_items = []
    total_amount = Decimal("0.00")

    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 1)

        if not product_id:
            return {
                "created": False,
                "reason": "Each cart item must contain product_id.",
            }

        if not isinstance(quantity, int) or quantity <= 0:
            return {
                "created": False,
                "reason": (
                    f"Invalid quantity for product {product_id}."
                ),
            }

        try:
            parsed_product_id = UUID(str(product_id))
        except ValueError:
            return {
                "created": False,
                "reason": f"Invalid product_id: {product_id}.",
            }

        result = await db.execute(
            select(Product).where(
                Product.id == parsed_product_id
            )
        )

        product = result.scalar_one_or_none()

        if product is None:
            return {
                "created": False,
                "reason": (
                    f"Product {product_id} was not found."
                ),
            }

        if product.stock_qty < quantity:
            return {
                "created": False,
                "reason": (
                    f"Insufficient stock for "
                    f"{product.name}. "
                    f"Requested {quantity}, "
                    f"available {product.stock_qty}."
                ),
            }

        line_total = (
            Decimal(product.price) * quantity
        )

        total_amount += line_total

        validated_items.append(
            {
                "product_id": str(product.id),
                "name": product.name,
                "quantity": quantity,
                "unit_price": float(product.price),
                "line_total": float(line_total),
            }
        )

    total_amount = total_amount.quantize(
        Decimal("0.01")
    )

    # Razorpay expects the amount in paise.
    razorpay_amount = int(
        total_amount * Decimal("100")
    )

    try:
        client = razorpay.Client(
            auth=(
                settings.razorpay_key_id,
                settings.razorpay_key_secret,
            )
        )

        razorpay_order = client.order.create(
            {
                "amount": razorpay_amount,
                "currency": "INR",
                "receipt": f"shopagent-{uuid4()}",
            }
        )

    except Exception as exc:
        await db.rollback()

        return {
            "created": False,
            "reason": f"Razorpay order creation failed: {str(exc)}",
        }

    razorpay_order_id = razorpay_order["id"]

    order = Order(
        razorpay_order_id=razorpay_order_id,
        status="created",
        cart_json=validated_items,
        total_amount=total_amount,
    )

    db.add(order)

    await db.commit()
    await db.refresh(order)

    return {
        "created": True,
        "order_id": str(order.id),
        "razorpay_order_id": order.razorpay_order_id,
        "status": order.status,
        "cart": validated_items,
        "total_amount": float(order.total_amount),
        "currency": "INR",
        "razorpay_amount": razorpay_amount,
    }


async def mark_order_paid(
    db: AsyncSession,
    razorpay_order_id: str,
) -> dict:
    result = await db.execute(
        select(Order).where(
            Order.razorpay_order_id == razorpay_order_id
        )
    )

    order = result.scalar_one_or_none()

    if order is None:
        return {
            "updated": False,
            "reason": "Order not found.",
        }

    # Idempotency:
    # If Razorpay sends the same successful event again,
    # don't process it twice.
    if order.status == "paid":
        return {
            "updated": False,
            "already_paid": True,
            "order_id": str(order.id),
            "razorpay_order_id": order.razorpay_order_id,
            "status": order.status,
        }

    order.status = "paid"

    from datetime import datetime, timezone

    order.confirmed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(order)

    return {
        "updated": True,
        "already_paid": False,
        "order_id": str(order.id),
        "razorpay_order_id": order.razorpay_order_id,
        "status": order.status,
        "confirmed_at": order.confirmed_at.isoformat(),
    }