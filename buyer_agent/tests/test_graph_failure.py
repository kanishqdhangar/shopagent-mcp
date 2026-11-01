
import pytest

from nodes.budget_guardrail import budget_guardrail
from graph import route_on_failure


def make_state(product, budget):
    return {
        "chosen_product": product,
        "budget_ceiling": budget,
        "decision_log": [],
        "failure_reason": None,
        "order_status": "not_started",
    }


@pytest.mark.asyncio
async def test_product_within_budget_passes_guardrail():
    state = make_state(
        {"id": "product-1", "name": "Running Shoes", "price": 2500},
        3000,
    )

    result = await budget_guardrail(state)

    assert result["failure_reason"] is None
    assert result["decision_log"][-1].decision == "Budget check passed"
    assert route_on_failure({**state, **result}) == "proceed"


@pytest.mark.asyncio
async def test_product_exceeding_budget_is_blocked():
    state = make_state(
        {"id": "product-2", "name": "Expensive Running Shoes", "price": 3500},
        3000,
    )

    result = await budget_guardrail(state)

    assert result["failure_reason"] == "budget_exceeded"
    assert result["decision_log"][-1].decision == "Budget exceeded"
    assert route_on_failure({**state, **result}) == "failed"


@pytest.mark.asyncio
async def test_product_equal_to_budget_is_allowed():
    state = make_state(
        {"id": "product-3", "name": "Running Shoes", "price": 3000},
        3000,
    )

    result = await budget_guardrail(state)

    assert result["failure_reason"] is None
    assert result["decision_log"][-1].decision == "Budget check passed"


@pytest.mark.asyncio
async def test_missing_budget_does_not_block_purchase():
    state = make_state(
        {"id": "product-4", "name": "Running Shoes", "price": 4500},
        None,
    )

    result = await budget_guardrail(state)

    assert result["failure_reason"] is None
    assert result["decision_log"][-1].decision == "Budget check passed"


@pytest.mark.asyncio
async def test_missing_product_fails_guardrail():
    state = make_state(None, 3000)

    result = await budget_guardrail(state)

    assert result["failure_reason"] == "no_selected_product"
    assert result["decision_log"][-1].decision == "Budget check failed"
    assert route_on_failure({**state, **result}) == "failed"
