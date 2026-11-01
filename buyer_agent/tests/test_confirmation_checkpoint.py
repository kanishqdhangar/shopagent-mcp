
import pytest
from uuid import uuid4

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from state import AgentState
from nodes.confirm_alternative import confirm_alternative


@pytest.fixture
def checkout_calls():
    return []


@pytest.fixture
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


async def build_test_graph(checkout_calls):
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

    async with AsyncRedisSaver(redis_url="redis://redis:6379") as checkpointer:
        await checkpointer.asetup()
        graph = builder.compile(checkpointer=checkpointer)

        return graph


@pytest.mark.asyncio
async def test_graph_pauses_and_resumes_after_approval(initial_state, checkout_calls):
    async with AsyncRedisSaver(redis_url="redis://redis:6379") as checkpointer:
        await checkpointer.asetup()

        async def mocked_checkout_alternative(state: AgentState):
            checkout_calls.append(state["pending_alternative"]["id"])
            return {
                "order_status": "created",
                "order_id": "mock-order-after-approval",
                "failure_reason": None,
            }

        builder = StateGraph(AgentState)
        builder.add_node("confirm_alternative", confirm_alternative)
        builder.add_node("checkout_alternative", mocked_checkout_alternative)
        builder.add_edge(START, "confirm_alternative")

        builder.add_conditional_edges(
            "confirm_alternative",
            lambda state: (
                "approved"
                if state.get("alternative_approved") is True
                else "rejected"
            ),
            {"approved": "checkout_alternative", "rejected": END},
        )
        builder.add_edge("checkout_alternative", END)

        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": f"approval-{uuid4()}"}}

        paused = await graph.ainvoke(initial_state, config=config)

        assert paused.get("__interrupt__")
        assert checkout_calls == []

        result = await graph.ainvoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert result["confirmation_status"] == "approved"
        assert result["alternative_approved"] is True
        assert result["order_status"] == "created"
        assert result["order_id"] == "mock-order-after-approval"
        assert checkout_calls == ["alternative-001"]


@pytest.mark.asyncio
async def test_graph_rejection_never_executes_checkout(initial_state, checkout_calls):
    async with AsyncRedisSaver(redis_url="redis://redis:6379") as checkpointer:
        await checkpointer.asetup()

        async def mocked_checkout_alternative(state: AgentState):
            checkout_calls.append(state["pending_alternative"]["id"])
            return {
                "order_status": "created",
                "order_id": "should-not-be-created",
                "failure_reason": None,
            }

        builder = StateGraph(AgentState)
        builder.add_node("confirm_alternative", confirm_alternative)
        builder.add_node("checkout_alternative", mocked_checkout_alternative)
        builder.add_edge(START, "confirm_alternative")

        builder.add_conditional_edges(
            "confirm_alternative",
            lambda state: (
                "approved"
                if state.get("alternative_approved") is True
                else "rejected"
            ),
            {"approved": "checkout_alternative", "rejected": END},
        )
        builder.add_edge("checkout_alternative", END)

        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": f"rejection-{uuid4()}"}}

        paused = await graph.ainvoke(initial_state, config=config)
        assert paused.get("__interrupt__")
        assert checkout_calls == []

        result = await graph.ainvoke(
            Command(resume={"approved": False}),
            config=config,
        )

        assert result["confirmation_status"] == "rejected"
        assert result["alternative_approved"] is False
        assert result["order_status"] == "cancelled"
        assert result["failure_reason"] == "alternative_rejected"
        assert checkout_calls == []
