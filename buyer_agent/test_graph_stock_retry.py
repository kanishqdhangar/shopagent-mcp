
import asyncio

import graph as graph_module
import nodes.checkout as checkout_module


PRIMARY = {
    "id": "product-1",
    "name": "Primary Running Shoes",
    "price": 2500.0,
    "category": "footwear",
    "subtype": "running",
    "stock_qty": 1,
}

ALTERNATIVE = {
    "id": "product-2",
    "name": "Alternative Running Shoes",
    "price": 2700.0,
    "category": "footwear",
    "subtype": "running",
    "stock_qty": 2,
}

order_calls = []
inventory_calls = []


async def fake_parse_intent(state):
    return {
        "parsed_filters": {
            "intent_type": "search",
            "category": "footwear",
            "subtype": "running",
            "budget": 3000.0,
            "search_query": "running shoes",
        },
        "budget_ceiling": 3000.0,
        "decision_log": state["decision_log"],
    }


async def fake_rag_search(state):
    return {
        "candidates": [PRIMARY, ALTERNATIVE],
        "decision_log": state["decision_log"],
    }


async def fake_compare_options(state):
    return {
        "chosen_product": PRIMARY,
        "confidence": 0.95,
        "decision_log": state["decision_log"],
    }


async def fake_check_upsell(state):
    return {
        "upsell_offer": None,
        "decision_log": state["decision_log"],
    }


async def fake_create_order(items):
    order_calls.append(items)
    product_id = items[0]["product_id"]

    if product_id == "product-1":
        return {
            "created": False,
            "error_code": "INSUFFICIENT_STOCK",
            "reason": "Primary product is out of stock.",
        }

    if product_id == "product-2":
        return {
            "created": True,
            "order_id": "mock-order-123",
        }

    raise AssertionError(f"Unexpected product: {product_id}")


async def fake_check_inventory(product_id):
    inventory_calls.append(product_id)

    return {
        "product_id": product_id,
        "stock_qty": 2,
        "in_stock": True,
    }


async def fake_confirm(state):
    # Avoid calling the seller or payment provider.
    return {
        "order_status": "paid",
        "order_id": state.get("order_id"),
        "failure_reason": None,
        "decision_log": state["decision_log"],
    }


async def main():
    order_calls.clear()
    inventory_calls.clear()

    # Mock upstream LLM/catalog nodes and payment confirmation.
    graph_module.parse_intent = fake_parse_intent
    graph_module.rag_search = fake_rag_search
    graph_module.compare_options = fake_compare_options
    graph_module.check_upsell = fake_check_upsell
    graph_module.confirm = fake_confirm

    # Keep the real checkout node, but mock its external MCP calls.
    checkout_module.create_order = fake_create_order
    checkout_module.check_inventory = fake_check_inventory

    app = await graph_module.build_buyer_graph()

    initial_state = {
        "goal": "Find running shoes under ₹3000.",
        "scenario": "budget_search",
        "parsed_filters": None,
        "candidates": [],
        "chosen_product": None,
        "upsell_offer": None,
        "confidence": 0.0,
        "budget_ceiling": 0.0,
        "order_status": "not_started",
        "order_id": None,
        "retry_count": 0,
        "decision_log": [],
        "failure_reason": None,
    }

    result = await app.ainvoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": "graph-stock-retry-test-20261030",
            }
        },
    )

    print("\n=== GRAPH STOCK RETRY TEST ===")
    print("Order attempts:", len(order_calls))
    print("Inventory checks:", inventory_calls)
    print("Final product:", result["chosen_product"]["name"])
    print("Order ID:", result["order_id"])
    print("Order status:", result["order_status"])
    print("Failure:", result["failure_reason"])

    print("\nDECISION LOG:")
    for entry in result["decision_log"]:
        print(entry.step, "|", entry.decision, "|", entry.reason)

    assert len(order_calls) == 2
    assert order_calls[0][0]["product_id"] == "product-1"
    assert order_calls[1][0]["product_id"] == "product-2"
    assert inventory_calls == ["product-2"]

    assert result["chosen_product"]["id"] == "product-2"
    assert result["order_id"] == "mock-order-123"
    assert result["order_status"] == "paid"
    assert result["failure_reason"] is None

    decisions = [entry.decision for entry in result["decision_log"]]

    assert "Budget check passed" in decisions
    assert "Stock failure detected" in decisions
    assert "Alternative product selected" in decisions
    assert "Order created after stock retry" in decisions

    print("\nPASS: Complete graph stock retry workflow succeeded.")


if __name__ == "__main__":
    asyncio.run(main())
