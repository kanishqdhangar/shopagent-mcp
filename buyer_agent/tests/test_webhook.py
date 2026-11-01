import asyncio
import httpx


WEBHOOK_URL = "http://seller:8000/webhooks/razorpay"


async def main():
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_invalid_signature_test",
                    "order_id": "order_invalid_test",
                    "amount": 289900,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }

    async with httpx.AsyncClient() as client:

        # Test 1: Invalid signature
        response = await client.post(
            WEBHOOK_URL,
            json=payload,
            headers={
                "X-Razorpay-Signature": "invalid-signature"
            },
        )

        print("\n=== INVALID SIGNATURE TEST ===")
        print("Status:", response.status_code)
        print("Response:", response.text)

        assert response.status_code == 400

        # Test 2: Missing signature
        response = await client.post(
            WEBHOOK_URL,
            json=payload,
        )

        print("\n=== MISSING SIGNATURE TEST ===")
        print("Status:", response.status_code)
        print("Response:", response.text)

        assert response.status_code == 400

    print("\nPASS: Both invalid and missing signature tests passed.")


if __name__ == "__main__":
    asyncio.run(main())