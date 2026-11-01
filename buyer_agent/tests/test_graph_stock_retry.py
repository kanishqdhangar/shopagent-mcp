
import pytest
from uuid import uuid4

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

import nodes.checkout as checkout_module
import nodes.checkout_alternative as alternative_module
from nodes.confirm_alternative import confirm_alternative
from state import AgentState


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


@pytest.fixture
def initial_state():
    return {
        "goal": "Buy running shoes under 3000",
        "scenario": "purchase",
        "parsed_filters": {"intent_type": "purchase"},
        "candidates": [PRIMARY, ALTERNATIVE],
        "chosen_product": PRIMARY,
        "upsell_offer": None,
        "confidence": 0.95,
        "retry_count": 0,
        "budget_ceiling": 3000.0,
        "order_status": "not_started",
        "order_id": None,
        "pending_alternative": None,
        "alternative_approved": False,
        "confirmation_status": "not_required",
        "decision_log": [],
        "failure_reason": None,
    }


@pytest.fixture
def order_calls():
    return []


@pytest.fixture
def inventory_calls():
    return []


@pytest.fixture
def checkout_calls():
    return []


@pytest.fixture
def mock_seller(monkeypatch, order_calls, inventory_calls):
    async def fake_create_order(items):
        order_calls.append(items)
        product_id = items[0]["product_id"]

        if product_id == PRIMARY["id"]:
            return {
                "created": False,
                "error_code": "INSUFFICIENT_STOCK",
                "reason": "Primary product is out of stock.",
            }

        if product_id == ALTERNATIVE["id"]:
            return {
                "created": True,
                "order_id": "mock-alternative-order",
            }

        raise AssertionError(f"Unexpected product ID: {product_id}")

    async def fake_check_inventory(product_id):
        inventory_calls.append(product_id)
        return {
            "product_id": product_id,
            "stock_qty": 2,
            "in_stock": True,
        }

    monkeypatch.setattr(checkout_module, "create_order", fake_create_order)
    monkeypatch.setattr(checkout_module, "check_inventory", fake_check_inventory)

    monkeypatch.setattr(alternative_module, "create_order", fake_create_order)
    monkeypatch.setattr(alternative_module, "check_inventory", fake_check_inventory)


async def build_stock_retry_graph():
    builder = StateGraph(AgentState)

    builder.add_node("checkout", checkout_module.checkout)
    builder.add_node("confirm_alternative", confirm_alternative)
    builder.add_node(
        "checkout_alternative",
        alternative_module.checkout_alternative,
    )

    builder.add_edge(START, "checkout")

    def route_after_checkout(state):
        if state.get("failure_reason"):
            return "failed"
        if state.get("order_status") == "awaiting_confirmation":
            return "needs_confirmation"
        return "failed"

    builder.add_conditional_edges(
        "checkout",
        route_after_checkout,
        {
            "failed": END,
            "needs_confirmation": "confirm_alternative",
        },
    )

    builder.add_conditional_edges(
        "confirm_alternative",
        lambda state: (
            "approved"
            if (
                state.get("alternative_approved") is True
                and state.get("confirmation_status") == "approved"
            )
            else "rejected"
        ),
        {
            "approved": "checkout_alternative",
            "rejected": END,
        },
    )

    builder.add_edge("checkout_alternative", END)

    return builder


@pytest.mark.asyncio
async def test_stock_failure_pauses_without_ordering_alternative(
    initial_state,
    mock_seller,
    order_calls,
    inventory_calls,
    checkout_calls,
):
    builder = await build_stock_retry_graph()

    async with AsyncRedisSaver(redis_url="redis://redis:6379") as checkpointer:
        await checkpointer.asetup()
        graph = builder.compile(checkpointer=checkpointer)

        config = {
            "configurable": {"thread_id": f"stock-pending-{uuid4()}"}
        }

        result = await graph.ainvoke(initial_state, config=config)

        assert result.get("__interrupt__")
        assert result["order_status"] == "awaiting_confirmation"
        assert result["pending_alternative"]["id"] == ALTERNATIVE["id"]
        assert result["alternative_approved"] is False
        assert result["order_id"] is None

        assert len(order_calls) == 1
        assert order_calls[0][0]["product_id"] == PRIMARY["id"]
        assert inventory_calls == [ALTERNATIVE["id"]]
        assert checkout_calls == []


@pytest.mark.asyncio
async def test_approved_alternative_is_ordered_exactly_once(
    initial_state,
    mock_seller,
    order_calls,
    inventory_calls,
    checkout_calls,
):
    builder = await build_stock_retry_graph()

    async with AsyncRedisSaver(redis_url="redis://redis:6379") as checkpointer:
        await checkpointer.asetup()
        graph = builder.compile(checkpointer=checkpointer)

        config = {
            "configurable": {"thread_id": f"stock-approved-{uuid4()}"}
        }

        paused = await graph.ainvoke(initial_state, config=config)
        assert paused.get("__interrupt__")
        assert len(order_calls) == 1

        result = await graph.ainvoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert result["confirmation_status"] == "approved"
        assert result["alternative_approved"] is True
        assert result["chosen_product"]["id"] == ALTERNATIVE["id"]
        assert result["order_status"] == "created"
        assert result["order_id"] == "mock-alternative-order"
        assert result["failure_reason"] is None

        assert len(order_calls) == 2
        assert order_calls[0][0]["product_id"] == PRIMARY["id"]
        assert order_calls[1][0]["product_id"] == ALTERNATIVE["id"]

        # Alternative inventory is checked once before offering it
        # and again after approval, immediately before ordering.
        assert inventory_calls == [ALTERNATIVE["id"], ALTERNATIVE["id"]]


@pytest.mark.asyncio
async def test_rejected_alternative_is_never_ordered(
    initial_state,
    mock_seller,
    order_calls,
    inventory_calls,
    checkout_calls,
):
    builder = await build_stock_retry_graph()

    async with AsyncRedisSaver(redis_url="redis://redis:6379") as checkpointer:
        await checkpointer.asetup()
        graph = builder.compile(checkpointer=checkpointer)

        config = {
            "configurable": {"thread_id": f"stock-rejected-{uuid4()}"}
        }

        paused = await graph.ainvoke(initial_state, config=config)
        assert paused.get("__interrupt__")

        result = await graph.ainvoke(
            Command(resume={"approved": False}),
            config=config,
        )

        assert result["confirmation_status"] == "rejected"
        assert result["alternative_approved"] is False
        assert result["order_status"] == "cancelled"
        assert result["failure_reason"] == "alternative_rejected"

        assert len(order_calls) == 1
        assert order_calls[0][0]["product_id"] == PRIMARY["id"]
        assert inventory_calls == [ALTERNATIVE["id"]]
