import asyncio

import graph as graph_module
from graph import build_buyer_graph


async def fake_parse_intent(state):
    return {
        "parsed_filters": {
            "intent_type": "search",
            "category": "running",
            "subtype": "shoe",
            "budget": 3000.0,
            "product_names": [],
            "search_query": "running shoe",
        },
        "budget_ceiling": 3000.0,
        "decision_log": state["decision_log"],
    }


async def fake_rag_search(state):
    return {
        "candidates": [],
        "decision_log": state["decision_log"],
    }


async def fake_compare_options(state):
    return {
        "chosen_product": {
            "id": "test-product-id",
            "name": "Running Shoe",
            "price": "2500.00",
            "stock_qty": 10,
        },
        "confidence": 0.95,
        "decision_log": state["decision_log"],
    }


async def fake_checkout(state):
    return {
        "order_status": "failed",
        "failure_reason": "order_creation_failed",
        "decision_log": state["decision_log"],
    }


async def fake_confirm(state):
    raise AssertionError(
        "Confirm must not execute when checkout fails!"
    )


async def main():
    graph_module.parse_intent = fake_parse_intent
    graph_module.rag_search = fake_rag_search
    graph_module.compare_options = fake_compare_options
    graph_module.checkout = fake_checkout
    graph_module.confirm = fake_confirm

    graph = await build_buyer_graph()

    result = await graph.ainvoke(
        {
            "goal": "Find a running shoe under ₹3000.",
            "scenario": "budget_search",
            "parsed_filters": None,
            "candidates": [],
            "chosen_product": None,
            "confidence": 0.0,
            "upsell_offer": None,
            "budget_ceiling": 0.0,
            "order_status": "not_started",
            "order_id": None,
            "decision_log": [],
            "failure_reason": None,
        },
        config={
            "configurable": {
                "thread_id": "checkout-failure-test",
            }
        },
    )

    print("\n=== CHECKOUT FAILURE TEST ===")
    print("Failure:", result["failure_reason"])
    print("Order status:", result["order_status"])

    print("\nDECISION LOG:")
    for entry in result["decision_log"]:
        print(entry.model_dump())


if __name__ == "__main__":
    asyncio.run(main())