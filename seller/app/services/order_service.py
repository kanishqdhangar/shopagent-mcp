import razorpay

from decimal import Decimal
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuditLog, Order, PaymentEvent, PaymentResumeOutbox, Product
from app.payment_security import validate_payment_event

from app.services.product_service import decrement_inventory
from app.services.discount_service import quote_discount

async def create_order(
    db: AsyncSession,
    items: list[dict],
    graph_thread_id: str | None = None,
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
                "error_code": "INSUFFICIENT_STOCK",
                "reason": (
                    f"Insufficient stock for "
                    f"{product.name}. "
                    f"Requested {quantity}, "
                    f"available {product.stock_qty}."
                ),
                "product_id": str(product.id),
                "available_stock": product.stock_qty,
            }

        try:
            discount_percent = Decimal(str(item.get("discount_percent", 0)))
            if not discount_percent.is_finite() or discount_percent < 0:
                raise ValueError("Discount percent must be a finite non-negative number.")
            if discount_percent > Decimal(str(settings.max_discount_percent)):
                raise ValueError(f"Discount exceeds seller maximum of {settings.max_discount_percent:.2f}%.")
            original_unit_price = Decimal(product.price).quantize(Decimal("0.01"))
            expected_price = item.get("expected_original_price")
            if expected_price is not None and Decimal(str(expected_price)).quantize(Decimal("0.01")) != original_unit_price:
                raise ValueError("Catalog price changed since the offer was made; request a fresh offer.")
        except (ValueError, ArithmeticError) as exc:
            return {"created": False, "error_code": "DISCOUNT_REJECTED", "reason": str(exc)}

        unit_price = quote_discount(original_unit_price, discount_percent)
        line_total = unit_price * quantity

        total_amount += line_total

        validated_items.append(
            {
                "product_id": str(product.id),
                "name": product.name,
                "quantity": quantity,
                "original_unit_price": float(original_unit_price),
                "discount_percent": float(discount_percent),
                "unit_price": float(unit_price),
                "line_total": float(line_total),
            }
        )

    total_amount = total_amount.quantize(
        Decimal("0.01")
    )

    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        return {"created": False, "reason": "Razorpay payment credentials are not configured."}

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
        graph_thread_id=graph_thread_id,
        payment_status="pending",
        currency="INR",
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
        "razorpay_key_id": settings.razorpay_key_id,
    }

async def get_order(
    db: AsyncSession,
    order_id: UUID,
) -> dict | None:
    result = await db.execute(
        select(Order).where(
            Order.id == order_id
        )
    )

    order = result.scalar_one_or_none()

    if order is None:
        return None

    return {
        "order_id": str(order.id),
        "razorpay_order_id": order.razorpay_order_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at.isoformat()
        if order.created_at
        else None,
        "confirmed_at": (
            order.confirmed_at.isoformat()
            if order.confirmed_at
            else None
        ),
        "cart": order.cart_json,
        "payment_status": order.payment_status,
        "razorpay_payment_id": order.razorpay_payment_id,
        "currency": order.currency,
    }


async def process_payment_webhook(
    db: AsyncSession,
    *,
    event_id: str,
    event_type: str,
    razorpay_order_id: str,
    razorpay_payment_id: str | None,
    amount: int | None,
    currency: str | None,
    captured: bool,
    payload: dict,
) -> dict:
    """Atomically record a verified Razorpay event and queue graph resumption."""
    existing = await db.execute(select(PaymentEvent).where(PaymentEvent.razorpay_event_id == event_id).with_for_update())
    if existing.scalar_one_or_none():
        await db.rollback()
        return {"processed": False, "duplicate": True}

    result = await db.execute(select(Order).where(Order.razorpay_order_id == razorpay_order_id).with_for_update())
    order = result.scalar_one_or_none()
    if order is None:
        await db.rollback()
        return {"processed": False, "reason": "Order not found."}

    validation_error = validate_payment_event(
        expected_amount=Decimal(order.total_amount),
        expected_currency=order.currency,
        amount=amount,
        currency=currency,
        event_type=event_type,
        captured=captured,
    )
    if validation_error:
        await db.rollback()
        return {"processed": False, "reason": validation_error}

    next_status = "paid" if captured else "failed"
    should_resume = order.payment_status != next_status
    if order.payment_status == "paid" and next_status != "paid":
        await db.rollback()
        return {"processed": False, "ignored": True, "status": "paid"}

    # Record the event idempotently. The unique constraint is the final
    # guard for concurrent webhook deliveries.
    event = PaymentEvent(
        razorpay_event_id=event_id,
        event_type=event_type,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        status=next_status,
        payload=payload,
    )
    db.add(event)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {"processed": False, "duplicate": True}

    if next_status == "paid" and order.payment_status != "paid":
        cart = order.cart_json
        if not isinstance(cart, list):
            await db.rollback()
            return {"processed": False, "reason": "Invalid order cart."}
        for item in cart:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)
            if not product_id or not isinstance(quantity, int) or quantity <= 0:
                await db.rollback()
                return {"processed": False, "reason": "Invalid order item."}
            try:
                parsed_product_id = UUID(str(product_id))
            except ValueError:
                await db.rollback()
                return {"processed": False, "reason": "Invalid product ID in order."}
            if not await decrement_inventory(db, parsed_product_id, quantity):
                await db.rollback()
                return {"processed": False, "reason": "Insufficient stock while confirming payment."}
        from datetime import datetime, timezone
        order.status = "paid"
        order.payment_status = "paid"
        order.confirmed_at = datetime.now(timezone.utc)
        order.razorpay_payment_id = razorpay_payment_id
    elif next_status == "failed" and order.payment_status != "paid":
        order.status = "payment_failed"
        order.payment_status = "failed"
        order.razorpay_payment_id = razorpay_payment_id

    if order.graph_thread_id and should_resume:
        db.add(PaymentResumeOutbox(
            payment_event_id=event.id,
            thread_id=order.graph_thread_id,
            order_id=order.id,
            payment_status=next_status,
        ))
        try:
            run_id = UUID(order.graph_thread_id)
        except ValueError:
            run_id = UUID(int=0)
        db.add(AuditLog(
            run_id=run_id,
            node_name="razorpay_webhook",
            decision=f"Payment {next_status}",
            reasoning=f"Verified {event_type} event {event_id} for order {order.id}.",
            tokens_used=0,
            latency_ms=0,
        ))

    await db.commit()
    return {"processed": True, "duplicate": False, "order_id": str(order.id), "status": order.status, "payment_status": order.payment_status}


async def reconcile_pending_payments(db: AsyncSession, limit: int = 25) -> int:
    """Recover payments if Razorpay's webhook delivery was missed."""
    import asyncio

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
    result = await db.execute(
        select(Order).where(
            Order.status.in_(["created", "payment_failed"]),
            Order.created_at <= cutoff,
            Order.razorpay_order_id.is_not(None),
        ).order_by(Order.created_at).limit(limit)
    )
    orders = result.scalars().all()
    if not orders:
        return 0

    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    reconciled = 0
    for order in orders:
        try:
            response = await asyncio.to_thread(client.order.payments, order.razorpay_order_id)
            payments = response.get("items", []) if isinstance(response, dict) else []
        except Exception:
            continue
        captured = next((p for p in payments if p.get("status") == "captured"), None)
        payment = captured
        if payment is None and payments and all(p.get("status") == "failed" for p in payments):
            payment = payments[-1]
        if not payment:
            continue
        status = payment.get("status")
        event_type = "payment.captured" if status == "captured" else "payment.failed"
        result = await process_payment_webhook(
            db,
            event_id=f"reconcile:{payment.get('id')}",
            event_type=event_type,
            razorpay_order_id=order.razorpay_order_id,
            razorpay_payment_id=payment.get("id"),
            amount=int(payment["amount"]) if payment.get("amount") is not None else None,
            currency=payment.get("currency"),
            captured=status == "captured",
            payload={"source": "razorpay_reconciliation", "payment": payment},
        )
        if result.get("processed"):
            reconciled += 1
    return reconciled
