
import pytest
from unittest.mock import AsyncMock

import nodes.checkout_alternative as checkout_module


@pytest.fixture
def approved_state():
    return {
        "pending_alternative": {
            "id": "product-2",
            "name": "Alternative Shoes",
            "price": 2700,
            "stock_qty": 2,
        },
        "alternative_approved": True,
        "confirmation_status": "approved",
        "budget_ceiling": 3000,
        "decision_log": [],
    }


@pytest.mark.asyncio
async def test_approved_alternative_creates_order(monkeypatch, approved_state):
    mock_inventory = AsyncMock(return_value={
        "product_id": "product-2",
        "stock_qty": 2,
        "in_stock": True,
    })

    mock_create_order = AsyncMock(return_value={
        "created": True,
        "order_id": "order-123",
    })

    monkeypatch.setattr(checkout_module, "check_inventory", mock_inventory)
    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)

    result = await checkout_module.checkout_alternative(approved_state)

    mock_inventory.assert_awaited_once_with("product-2")
    mock_create_order.assert_awaited_once_with(
        items=[{"product_id": "product-2", "quantity": 1}]
    )

    assert result["order_status"] == "created"
    assert result["order_id"] == "order-123"
    assert result["chosen_product"]["id"] == "product-2"
    assert result["failure_reason"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "approval, confirmation",
    [
        (False, "approved"),
        (True, "pending"),
        (True, "rejected"),
        (None, "approved"),
    ],
)
async def test_checkout_blocked_without_valid_approval(
    monkeypatch, approved_state, approval, confirmation
):
    approved_state["alternative_approved"] = approval
    approved_state["confirmation_status"] = confirmation

    mock_inventory = AsyncMock()
    mock_create_order = AsyncMock()

    monkeypatch.setattr(checkout_module, "check_inventory", mock_inventory)
    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)

    result = await checkout_module.checkout_alternative(approved_state)

    assert result["failure_reason"] == "alternative_not_approved"
    mock_inventory.assert_not_awaited()
    mock_create_order.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inventory",
    [
        {"error": "Inventory unavailable"},
        {"in_stock": False, "stock_qty": 0},
        {"in_stock": True, "stock_qty": 0},
    ],
)
async def test_checkout_blocked_when_alternative_unavailable(
    monkeypatch, approved_state, inventory
):
    mock_inventory = AsyncMock(return_value=inventory)
    mock_create_order = AsyncMock()

    monkeypatch.setattr(checkout_module, "check_inventory", mock_inventory)
    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)

    result = await checkout_module.checkout_alternative(approved_state)

    assert result["failure_reason"] == "alternative_out_of_stock"
    mock_create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_checkout_blocked_when_budget_exceeded(monkeypatch, approved_state):
    approved_state["budget_ceiling"] = 2000

    mock_inventory = AsyncMock()
    mock_create_order = AsyncMock()

    monkeypatch.setattr(checkout_module, "check_inventory", mock_inventory)
    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)

    result = await checkout_module.checkout_alternative(approved_state)

    assert result["failure_reason"] == "budget_exceeded"
    mock_inventory.assert_not_awaited()
    mock_create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_inventory_exception_blocks_checkout(monkeypatch, approved_state):
    mock_inventory = AsyncMock(side_effect=Exception("Database unavailable"))
    mock_create_order = AsyncMock()

    monkeypatch.setattr(checkout_module, "check_inventory", mock_inventory)
    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)

    result = await checkout_module.checkout_alternative(approved_state)

    assert result["failure_reason"] == "inventory_check_failed"
    mock_create_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_creation_failure(monkeypatch, approved_state):
    mock_inventory = AsyncMock(return_value={
        "in_stock": True,
        "stock_qty": 2,
    })

    mock_create_order = AsyncMock(return_value={
        "created": False,
        "reason": "Seller rejected order",
    })

    monkeypatch.setattr(checkout_module, "check_inventory", mock_inventory)
    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)

    result = await checkout_module.checkout_alternative(approved_state)

    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "alternative_order_failed"
    assert result["order_id"] is None


@pytest.mark.asyncio
async def test_missing_alternative_id_blocks_checkout(
    monkeypatch, approved_state
):
    approved_state["pending_alternative"].pop("id")

    mock_inventory = AsyncMock()
    mock_create_order = AsyncMock()

    monkeypatch.setattr(checkout_module, "check_inventory", mock_inventory)
    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)

    result = await checkout_module.checkout_alternative(approved_state)

    assert result["failure_reason"] == "invalid_alternative"
    mock_inventory.assert_not_awaited()
    mock_create_order.assert_not_awaited()
