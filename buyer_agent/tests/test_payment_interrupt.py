from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from nodes.await_payment import await_payment
from state import AgentState


def graph():
    builder = StateGraph(AgentState)
    builder.add_node("await_payment", await_payment)
    builder.add_edge(START, "await_payment")
    builder.add_edge("await_payment", END)
    return builder.compile(checkpointer=InMemorySaver())


def state():
    return {
        "run_id": str(uuid4()), "thread_id": str(uuid4()), "goal": "buy product",
        "scenario": "purchase", "parsed_filters": {"intent_type": "purchase"},
        "candidates": [], "chosen_product": {"id": "product-1"}, "upsell_offer": None,
        "confidence": 0.9, "retry_count": 0, "budget_ceiling": None,
        "order_status": "created", "order_id": "internal-order-1",
        "payment_details": {"razorpay_order_id": "rzp-order-1"}, "payment_status": "pending",
        "pending_alternative": None, "alternative_approved": False,
        "confirmation_status": "not_required", "decision_log": [], "failure_reason": None,
    }


@pytest.mark.asyncio
async def test_payment_interrupt_resumes_to_paid_state():
    compiled = graph()
    config = {"configurable": {"thread_id": str(uuid4())}}
    paused = await compiled.ainvoke(state(), config=config)
    assert paused["__interrupt__"][0].value["type"] == "payment_required"
    result = await compiled.ainvoke(Command(resume={"payment_status": "paid"}), config=config)
    assert result["payment_status"] == "paid"
    assert result["order_status"] == "paid"


@pytest.mark.asyncio
async def test_payment_interrupt_resumes_to_failure_state():
    compiled = graph()
    config = {"configurable": {"thread_id": str(uuid4())}}
    await compiled.ainvoke(state(), config=config)
    result = await compiled.ainvoke(Command(resume={"payment_status": "failed"}), config=config)
    assert result["payment_status"] == "failed"
    assert result["order_status"] == "failed"
