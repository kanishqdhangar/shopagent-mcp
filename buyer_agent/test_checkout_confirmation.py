
import asyncio
from unittest.mock import AsyncMock, patch

from nodes.checkout import checkout


async def main():
    original_product = {
        "id": "original-001",
        "name": "CoolMesh Running Socks",
        "price": "449.00",
        "stock_qty": 0,
    }

    alternative_product = {
        "id": "alternative-001",
        "name": "CushionStep Running Socks",
        "price": "499.00",
        "stock_qty": 34,
    }

    state = {
        "goal": "Reorder my usual CoolMesh Running Socks",
        "scenario": "restock_or_compare",
        "parsed_filters": {"intent_type": "restock"},
        "candidates": [original_product, alternative_product],
        "chosen_product": original_product,
        "upsell_offer": None,
        "confidence": 0.9,
        "retry_count": 0,
        "budget_ceiling": 1000.0,
        "order_status": "not_started",
        "order_id": None,
        "pending_alternative": None,
        "alternative_approved": False,
        "confirmation_status": "not_required",
        "decision_log": [],
        "failure_reason": None,
    }

    # Original product fails due to insufficient stock.
    mock_create_order = AsyncMock(
        return_value={
            "created": False,
            "error_code": "INSUFFICIENT_STOCK",
            "reason": "Insufficient stock",
        }
    )

    mock_check_inventory = AsyncMock(
        return_value={
            "in_stock": True,
            "stock_qty": 34,
        }
    )

    with (
        patch("nodes.checkout.create_order", mock_create_order),
        patch("nodes.checkout.check_inventory", mock_check_inventory),
    ):
        result = await checkout(state)

    print("\n--- CHECKOUT CONFIRMATION TEST ---")
    print("Order status:", result["order_status"])
    print(
        "Pending alternative:",
        result["pending_alternative"]["name"],
    )
    print(
        "Confirmation status:",
        result["confirmation_status"],
    )
    print("Order ID:", result["order_id"])
    print("Create-order calls:", mock_create_order.await_count)

    assert result["order_status"] == "awaiting_confirmation"
    assert result["confirmation_status"] == "pending"
    assert result["pending_alternative"]["id"] == "alternative-001"
    assert result["order_id"] is None

    # Only the original product was submitted.
    assert mock_create_order.await_count == 1

    # Alternative inventory was checked, but it was not purchased.
    mock_check_inventory.assert_awaited_once_with("alternative-001")

    print("\nPASS: Alternative requires explicit user approval.")


if __name__ == "__main__":
    asyncio.run(main())
