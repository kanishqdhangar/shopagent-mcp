import asyncio

from graph import build_buyer_graph


async def main():
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
                "thread_id": "graph-test-001",
            }
        },
    )

    print("\n=== FINAL STATE ===")

    print("\nPARSED FILTERS:")
    print(result["parsed_filters"])

    print("\nCANDIDATES:")
    for product in result["candidates"]:
        print(
            product["name"],
            "| ₹",
            product["price"],
            "| stock:",
            product["stock_qty"],
        )

    print("\nCHOSEN PRODUCT:")
    print(result["chosen_product"])

    print("\nCONFIDENCE:")
    print(result.get("confidence"))
    
    print("\nFAILURE:")
    print(result["failure_reason"])

    print("\nDECISION LOG:")

    for entry in result["decision_log"]:
        print(entry.model_dump())


if __name__ == "__main__":
    asyncio.run(main())