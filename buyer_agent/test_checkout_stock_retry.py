
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
async def test_stock_failure_retries_with_alternative(monkeypatch, initial_state):
    calls = []

    async def mock_create_order(items):
        calls.append(items)
        if len(calls) == 1:
            return {
                "created": False,
                "error_code": "INSUFFICIENT_STOCK",
                "reason": "Primary product is out of stock",
            }

        return {"created": True, "order_id": "order-123"}

    async def mock_check_inventory(product_id):
        assert product_id == "product-2"
        return {
            "product_id": product_id,
            "stock_qty": 2,
            "in_stock": True,
        }

    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)
    monkeypatch.setattr(checkout_module, "check_inventory", mock_check_inventory)

    result = await checkout_module.checkout(initial_state)

    assert len(calls) == 2
    assert result["order_status"] == "created"
    assert result["order_id"] == "order-123"
    assert result["chosen_product"]["id"] == "product-2"
    assert result["failure_reason"] is None



@pytest.mark.asyncio
async def test_retry_fails_if_alternative_stock_changes(
    monkeypatch, initial_state
):
    calls = []

    async def mock_create_order(items):
        calls.append(items)

        # Both order attempts fail due to insufficient stock.
        return {
            "created": False,
            "error_code": "INSUFFICIENT_STOCK",
            "reason": "Product became unavailable",
        }

    async def mock_check_inventory(product_id):
        # Alternative appears available during inventory check.
        return {
            "product_id": product_id,
            "stock_qty": 2,
            "in_stock": True,
        }

    monkeypatch.setattr(checkout_module, "create_order", mock_create_order)
    monkeypatch.setattr(checkout_module, "check_inventory", mock_check_inventory)

    result = await checkout_module.checkout(initial_state)

    assert len(calls) == 2
    assert calls[0][0]["product_id"] == "product-1"
    assert calls[1][0]["product_id"] == "product-2"

    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "insufficient_stock_after_retry"
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
