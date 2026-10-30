import asyncio

from graph import build_buyer_graph
import nodes.budget_guardrail as guardrail_module


async def fake_parse_intent(state):
    return {
        "parsed_filters": {
            "intent_type": "search",
            "category": "running",
            "subtype": "shoe",
            "budget": 3000.0,
            "product_names": [],
            "search_query": "expensive running shoe",
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
            "name": "Expensive Running Shoe",
            "price": "3500.00",
            "stock_qty": 10,
        },
        "confidence": 0.95,
        "decision_log": state["decision_log"],
    }


async def fake_checkout(state):
    raise AssertionError(
        "Checkout must not execute when budget is exceeded!"
    )


async def main():
    import graph as graph_module

    graph_module.parse_intent = fake_parse_intent
    graph_module.rag_search = fake_rag_search
    graph_module.compare_options = fake_compare_options
    graph_module.checkout = fake_checkout

    graph = await build_buyer_graph()

    result = await graph.ainvoke(
        {
            "goal": "Find an expensive running shoe.",
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
                "thread_id": "budget-failure-test",
            }
        },
    )

    print("\n=== GRAPH FAILURE TEST ===")
    print("Failure:", result["failure_reason"])
    print("Order status:", result["order_status"])

    print("\nDECISION LOG:")
    for entry in result["decision_log"]:
        print(entry.model_dump())


if __name__ == "__main__":
    asyncio.run(main())