import asyncio

from nodes.checkout import checkout


PRODUCT_ID = "eb5e2833-d31c-44d1-95b2-6ea108610b89"


async def main():
    state = {
        "goal": "Find me a lightweight running shoe under ₹3000.",
        "scenario": "budget_search",
        "parsed_filters": {
            "intent_type": "search",
            "category": "running",
            "subtype": "shoes",
            "budget": 3000.0,
            "product_names": [],
            "search_query": "lightweight running shoe",
        },
        "candidates": [],
        "chosen_product": {
            "id": PRODUCT_ID,
            "name": "AeroRun Lite Trainers",
            "category": "running",
            "subtype": "shoes",
            "price": "2899.00",
            "size": "UK 8",
            "stock_qty": 17,
            "description": (
                "Lightweight and breathable trainers "
                "designed for comfortable everyday runs."
            ),
        },
        "confidence": 0.95,
        "upsell_offer": None,
        "budget_ceiling": 3000.0,
        "order_status": "not_started",
        "order_id": None,
        "decision_log": [],
        "failure_reason": None,
    }

    result = await checkout(state)

    print("\n=== CHECKOUT TEST ===")

    print("\nORDER STATUS:")
    print(result.get("order_status"))

    print("\nORDER ID:")
    print(result.get("order_id"))

    print("\nFAILURE:")
    print(result.get("failure_reason"))

    print("\nDECISION LOG:")
    for entry in result["decision_log"]:
        print(entry.model_dump())


if __name__ == "__main__":
    asyncio.run(main())