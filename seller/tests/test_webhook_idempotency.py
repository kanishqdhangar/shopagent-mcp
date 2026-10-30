
import asyncio
import hashlib
import hmac
import json
import os
import sys

import httpx


async def main():
    if len(sys.argv) != 2:
        raise ValueError(
            "Usage: python test_webhook_idempotency.py <razorpay_order_id>"
        )

    razorpay_order_id = sys.argv[1]
    secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay-test-{razorpay_order_id}",
                    "order_id": razorpay_order_id,
                    "amount": 289900,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }

    body = json.dumps(payload, separators=(",", ":"))

    signature = hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature,
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(1, 3):
            response = await client.post(
                "http://localhost:8000/webhooks/razorpay",
                content=body,
                headers=headers,
            )

            print(f"\n=== WEBHOOK ATTEMPT {attempt} ===")
            print("HTTP status:", response.status_code)
            print("Response:", response.text)

            assert response.status_code == 200

    print("\nPASS: Both webhook requests were accepted.")


if __name__ == "__main__":
    asyncio.run(main())
