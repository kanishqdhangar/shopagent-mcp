
import asyncio
from uuid import uuid4

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from state import AgentState
from nodes.confirm_alternative import confirm_alternative


checkout_calls = []


async def mocked_checkout_alternative(state: AgentState):
    checkout_calls.append(state["pending_alternative"]["id"])

    return {
        "order_status": "created",
        "order_id": "mock-order-after-approval",
        "failure_reason": None,
    }


def route_after_decision(state: AgentState):
    if state.get("alternative_approved") is True:
        return "approved"
    return "rejected"


def initial_state():
    return {
        "goal": "Reorder my usual running socks",
        "scenario": "restock_or_compare",
        "parsed_filters": {"intent_type": "restock"},
        "candidates": [],
        "chosen_product": None,
        "upsell_offer": None,
        "confidence": 0.9,
        "retry_count": 0,
        "budget_ceiling": 1000.0,
        "order_status": "awaiting_confirmation",
        "order_id": None,
        "pending_alternative": {
            "id": "alternative-001",
            "name": "CushionStep Running Socks",
            "price": "499.00",
            "stock_qty": 34,
            "description": "Comfortable running socks",
        },
        "alternative_approved": False,
        "confirmation_status": "pending",
        "decision_log": [],
        "failure_reason": None,
    }


async def main():
    checkpointer = AsyncRedisSaver(
        redis_url="redis://redis:6379"
    )
    await checkpointer.asetup()

    builder = StateGraph(AgentState)

    builder.add_node("confirm_alternative", confirm_alternative)
    builder.add_node(
        "checkout_alternative",
        mocked_checkout_alternative,
    )

    builder.add_edge(START, "confirm_alternative")

    builder.add_conditional_edges(
        "confirm_alternative",
        route_after_decision,
        {
            "approved": "checkout_alternative",
            "rejected": END,
        },
    )

    builder.add_edge("checkout_alternative", END)

    graph = builder.compile(checkpointer=checkpointer)

    # ---------------------------------
    # TEST 1: APPROVAL
    # ---------------------------------
    print("\n--- APPROVAL TEST ---")

    approval_config = {
        "configurable": {
            "thread_id": f"approval-{uuid4()}"
        }
    }

    paused = await graph.ainvoke(
        initial_state(),
        config=approval_config,
    )

    assert paused.get("__interrupt__"), (
        "Graph did not pause for approval."
    )

    print("Graph paused:", bool(paused["__interrupt__"]))
    print("Checkout calls before approval:", len(checkout_calls))

    assert len(checkout_calls) == 0

    approved_result = await graph.ainvoke(
        Command(resume={"approved": True}),
        config=approval_config,
    )

    assert approved_result["confirmation_status"] == "approved"
    assert approved_result["alternative_approved"] is True
    assert approved_result["order_status"] == "created"
    assert approved_result["order_id"] == "mock-order-after-approval"

    assert len(checkout_calls) == 1
    assert checkout_calls[0] == "alternative-001"
    print("Confirmation:", approved_result["confirmation_status"])
    print("Order status:", approved_result["order_status"])
    print("Mock order ID:", approved_result["order_id"])
    print("Checkout calls after approval:", len(checkout_calls))

    # ---------------------------------
    # TEST 2: REJECTION
    # ---------------------------------
    print("\n--- REJECTION TEST ---")

    rejection_config = {
        "configurable": {
            "thread_id": f"rejection-{uuid4()}"
        }
    }

    calls_before_rejection = len(checkout_calls)

    paused = await graph.ainvoke(
        initial_state(),
        config=rejection_config,
    )

    assert paused.get("__interrupt__")

    rejected_result = await graph.ainvoke(
        Command(resume={"approved": False}),
        config=rejection_config,
    )

    assert rejected_result["confirmation_status"] == "rejected"
    assert rejected_result["order_status"] == "cancelled"
    assert rejected_result["failure_reason"] == "alternative_rejected"

    assert len(checkout_calls) == calls_before_rejection

    print("Confirmation:", rejected_result["confirmation_status"])
    print("Order status:", rejected_result["order_status"])
    print("Failure:", rejected_result["failure_reason"])
    print("Checkout calls:", len(checkout_calls))

    print("\nPASS: Redis-backed confirmation checkpoint works.")


if __name__ == "__main__":
    asyncio.run(main())
