import asyncio
import hashlib
import hmac
import json

import httpx

import nodes.checkout as checkout_module
from config import settings
from graph import build_buyer_graph
from tools.mcp_tools import create_order as real_create_order


async def create_order_and_trigger_webhook(*, items):
    """
    Test-only wrapper around the real create_order().

    1. Creates a real Razorpay test order.
    2. Immediately triggers our signed webhook.
    3. Returns the real create_order() response.
    """

    result = await real_create_order(items=items)

    razorpay_order_id = result.get("razorpay_order_id")

    if not razorpay_order_id:
        raise RuntimeError(
            "create_order did not return razorpay_order_id"
        )

    print("\n=== E2E PAYMENT ===")
    print("Created Razorpay order:", razorpay_order_id)

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay-e2e-{razorpay_order_id}",
                    "order_id": razorpay_order_id,
                    "amount": result["razorpay_amount"],
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
        "X-Razorpay-Event-Id": f"e2e-{razorpay_order_id}",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://seller:8000/webhooks/razorpay",
            content=body,
            headers=headers,
        )

    print("Webhook status:", response.status_code)
    print("Webhook response:", response.text)

    return result


async def main():
    # Patch only this test process.
    checkout_module.create_order = create_order_and_trigger_webhook

    graph = await build_buyer_graph()

    result = await graph.ainvoke(
        {
            "goal": "Find me a lightweight running shoe under ₹3000.",
            "scenario": "budget_search",
            "parsed_filters": None,
            "candidates": [],
            "chosen_product": None,
            "upsell_offer": None,
            "budget_ceiling": 0.0,
            "order_status": "not_started",
            "order_id": None,
            "decision_log": [],
            "failure_reason": None,
        },
        config={
            "configurable": {
                "thread_id": "e2e-payment-test",
            }
        },
    )

    print("\n=== E2E FINAL STATE ===")
    print("Order status:", result["order_status"])
    print("Order ID:", result["order_id"])
    print("Failure:", result["failure_reason"])

    print("\n=== DECISION LOG ===")

    for entry in result["decision_log"]:
        print(entry.model_dump())


if __name__ == "__main__":
    asyncio.run(main())