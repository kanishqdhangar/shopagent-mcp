
import asyncio
import uuid

from graph import build_buyer_graph


async def main():
    app = await build_buyer_graph()

    initial_state = {
        "goal": "Find me a lightweight running shoe under ₹3000.",
        "scenario": "budget_search",
        "retry_count": 0,
        "parsed_filters": None,
        "candidates": [],
        "chosen_product": None,
        "upsell_offer": None,
        "confidence": 0.0,
        "budget_ceiling": 0.0,
        "order_status": "not_started",
        "order_id": None,
        "decision_log": [],
        "failure_reason": None,
    }

    result = await app.ainvoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": f"e2e-payment-{uuid.uuid4()}",
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

    assert result["order_status"] == "paid", (
        f"Expected paid, got {result['order_status']}"
    )
    assert result["failure_reason"] is None
    assert result["order_id"] is not None

    print("\nPASS: Complete buyer payment workflow succeeded.")


if __name__ == "__main__":
    asyncio.run(main())
