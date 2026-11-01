import asyncio

from nodes.budget_guardrail import budget_guardrail


async def main():
    state = {
        "goal": "Find me a running shoe under ₹3000.",
        "scenario": "budget_search",
        "parsed_filters": {
            "intent_type": "search",
            "category": "running",
            "subtype": "shoes",
            "budget": 3000.0,
            "product_names": [],
            "search_query": "running shoes",
        },
        "candidates": [],
        "chosen_product": {
            "id": "test-product",
            "name": "Test Running Shoes",
            "price": "3500.00",
            "stock_qty": 10,
        },
        "upsell_offer": None,
        "budget_ceiling": 3000.0,
        "order_status": "not_started",
        "order_id": None,
        "decision_log": [],
        "failure_reason": None,
    }

    result = await budget_guardrail(state)

    print("\n=== BUDGET GUARDRAIL TEST ===")

    print("\nFAILURE:")
    print(result["failure_reason"])

    print("\nDECISION LOG:")
    for entry in result["decision_log"]:
        print(entry.model_dump())


if __name__ == "__main__":
    asyncio.run(main())