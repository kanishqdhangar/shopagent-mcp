import asyncio
import hashlib
import hmac
import json

import httpx

from config import settings


RAZORPAY_ORDER_ID = "order_TWr5qtD0wWEf3u"


async def main():
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_shopagent_001",
                    "order_id": RAZORPAY_ORDER_ID,
                    "amount": 289900,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
    )

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
            "http://seller:8000/webhooks/razorpay",
            content=body,
            headers=headers,
        )

    print("\n=== WEBHOOK RESPONSE ===")
    print("STATUS:", response.status_code)
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())