
import pytest

import nodes.checkout as checkout_module


@pytest.fixture
def initial_state():
    primary = {
        "id": "product-1",
        "name": "Primary Shoes",
        "price": 2500,
        "category": "footwear",
        "subtype": "running",
        "stock_qty": 1,
    }

    alternative = {
        "id": "product-2",
        "name": "Alternative Shoes",
        "price": 2700,
        "category": "footwear",
        "subtype": "running",
        "stock_qty": 2,
    }

    return {
        "chosen_product": primary,
        "candidates": [primary, alternative],
        "budget_ceiling": 3000,
        "decision_log": [],
    }



@pytest.mark.asyncio
async def test_stock_failure_offers_alternative_without_creating_order(
    monkeypatch, initial_state
):
    calls = []
    inventory_calls = []

    async def mock_create_order(items):
        calls.append(items)
        return {
            "created": False,
            "error_code": "INSUFFICIENT_STOCK",
            "reason": "Primary product is out of stock",
        }

    async def mock_check_inventory(product_id):
        inventory_calls.append(product_id)
        return {
            "product_id": product_id,
            "stock_qty": 2,
            "in_stock": True,
        }

    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)
    monkeypatch.setattr(checkout_module, "check_inventory", mock_check_inventory)

    result = await checkout_module.checkout(initial_state)

    assert len(calls) == 1
    assert calls[0][0]["product_id"] == "product-1"

    assert inventory_calls == ["product-2"]

    assert result["order_status"] == "awaiting_confirmation"
    assert result["confirmation_status"] == "pending"
    assert result["alternative_approved"] is False
    assert result["pending_alternative"]["id"] == "product-2"
    assert result["order_id"] is None


@pytest.mark.asyncio
async def test_alternative_is_not_ordered_before_user_approval(
    monkeypatch, initial_state
):
    calls = []

    async def mock_create_order(items):
        calls.append(items)
        return {
            "created": False,
            "error_code": "INSUFFICIENT_STOCK",
            "reason": "Primary product is out of stock",
        }

    async def mock_check_inventory(product_id):
        return {
            "product_id": product_id,
            "stock_qty": 2,
            "in_stock": True,
        }

    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)
    monkeypatch.setattr(checkout_module, "check_inventory", mock_check_inventory)

    result = await checkout_module.checkout(initial_state)

    assert len(calls) == 1
    assert result["pending_alternative"]["id"] == "product-2"
    assert result["alternative_approved"] is False
    assert result["order_id"] is None


@pytest.mark.asyncio
async def test_non_stock_failure_does_not_retry(monkeypatch, initial_state):
    calls = []

    async def mock_create_order(items):
        calls.append(items)
        return {
            "created": False,
            "error_code": "RAZORPAY_ERROR",
            "reason": "Payment provider unavailable",
        }

    async def mock_check_inventory(product_id):
        pytest.fail("Inventory should not be checked for non-stock failures")

    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)
    monkeypatch.setattr(checkout_module, "check_inventory", mock_check_inventory)

    result = await checkout_module.checkout(initial_state)

    assert len(calls) == 1
    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "order_creation_failed"


@pytest.mark.asyncio
async def test_no_alternative_does_not_retry(monkeypatch, initial_state):
    calls = []

    async def mock_create_order(items):
        calls.append(items)
        return {
            "created": False,
            "error_code": "INSUFFICIENT_STOCK",
            "reason": "Primary product is out of stock",
        }

    async def mock_check_inventory(product_id):
        pytest.fail("There should be no alternative to check")

    initial_state["candidates"] = [initial_state["chosen_product"]]

    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)
    monkeypatch.setattr(checkout_module, "check_inventory", mock_check_inventory)

    result = await checkout_module.checkout(initial_state)

    assert len(calls) == 1
    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "insufficient_stock_no_alternative"
