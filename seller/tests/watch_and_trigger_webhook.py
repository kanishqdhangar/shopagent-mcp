
import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Order


POLL_INTERVAL = 0.5
TIMEOUT_SECONDS = 180


async def find_new_order(started_at):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Order)
            .where(
                Order.status == "created",
                Order.created_at >= started_at,
                Order.razorpay_order_id.is_not(None),
            )
            .order_by(Order.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def main():
    if not settings.razorpay_webhook_secret:
        raise RuntimeError("Seller webhook secret is not configured.")

    started_at = datetime.now(timezone.utc)

    print("=== SELLER WEBHOOK WATCHER ===")
    print("Waiting for a newly created buyer order...")

    deadline = asyncio.get_running_loop().time() + TIMEOUT_SECONDS
    order = None

    while asyncio.get_running_loop().time() < deadline:
        order = await find_new_order(started_at)

        if order:
            break

        await asyncio.sleep(POLL_INTERVAL)

    if not order:
        raise TimeoutError(
            f"No new order detected within {TIMEOUT_SECONDS} seconds."
        )

    razorpay_order_id = order.razorpay_order_id
    amount = int(Decimal(order.total_amount) * 100)

    print("Detected order:", order.id)
    print("Razorpay order:", razorpay_order_id)
    print("Amount in paise:", amount)

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay-e2e-{razorpay_order_id}",
                    "order_id": razorpay_order_id,
                    "amount": amount,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }

    body = json.dumps(payload, separators=(",", ":"))

    signature = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/webhooks/razorpay",
            content=body,
            headers=headers,
        )

    print("\n=== WEBHOOK RESPONSE ===")
    print("HTTP status:", response.status_code)
    print("Response:", response.text)

    response.raise_for_status()

    result = response.json()

    if result.get("status") != "paid":
        raise AssertionError("Seller did not mark the order as paid.")

    print("\nPASS: Seller successfully processed the payment webhook.")


if __name__ == "__main__":
    asyncio.run(main())
