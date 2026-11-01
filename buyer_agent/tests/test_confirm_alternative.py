
import pytest
from unittest.mock import patch

from nodes.confirm_alternative import confirm_alternative


@pytest.fixture
def state():
    return {
        "pending_alternative": {
            "id": "product-2",
            "name": "Alternative Shoes",
            "price": 2700,
            "stock_qty": 2,
            "description": "Running shoes",
        },
        "decision_log": [],
    }


@pytest.mark.asyncio
async def test_explicit_approval(state):
    with patch(
        "nodes.confirm_alternative.interrupt",
        return_value={"approved": True},
    ) as mock_interrupt:
        result = await confirm_alternative(state)

    mock_interrupt.assert_called_once()

    assert result["alternative_approved"] is True
    assert result["confirmation_status"] == "approved"
    assert result["chosen_product"]["id"] == "product-2"


@pytest.mark.asyncio
async def test_explicit_rejection(state):
    with patch(
        "nodes.confirm_alternative.interrupt",
        return_value={"approved": False},
    ):
        result = await confirm_alternative(state)

    assert result["alternative_approved"] is False
    assert result["confirmation_status"] == "rejected"
    assert result["order_status"] == "cancelled"
    assert result["failure_reason"] == "alternative_rejected"
    assert result["order_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", [
    None,
    {},
    {"approved": "true"},
    {"approved": 1},
    {"approved": None},
])
async def test_only_boolean_true_counts_as_approval(state, decision):
    with patch(
        "nodes.confirm_alternative.interrupt",
        return_value=decision,
    ):
        result = await confirm_alternative(state)

    assert result["alternative_approved"] is False
    assert result["confirmation_status"] == "rejected"
    assert result["failure_reason"] == "alternative_rejected"


@pytest.mark.asyncio
async def test_missing_alternative_does_not_interrupt():
    state = {"pending_alternative": None, "decision_log": []}

    with patch("nodes.confirm_alternative.interrupt") as mock_interrupt:
        result = await confirm_alternative(state)

    mock_interrupt.assert_not_called()

    assert result["alternative_approved"] is False
    assert result["confirmation_status"] == "rejected"
    assert result["failure_reason"] == "no_pending_alternative"
