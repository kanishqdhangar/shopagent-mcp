
import time
from typing import Any

from state import AgentState, DecisionLogEntry
from tools.mcp_tools import create_order, check_inventory


async def checkout_alternative(state: AgentState) -> dict[str, Any]:
    started_at = time.perf_counter()
    decision_log = list(state.get("decision_log", []))

    def failure(reason: str, message: str):
        entry = DecisionLogEntry(
            step="checkout_alternative",
            decision="Alternative checkout failed",
            reason=message,
            tokens_used=0,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
        )

        return {
            "order_status": "failed",
            "order_id": None,
            "failure_reason": reason,
            "decision_log": [*decision_log, entry],
        }

    alternative = state.get("pending_alternative")

    # Never trust a state transition alone as proof of approval.
    if (
        state.get("alternative_approved") is not True
        or state.get("confirmation_status") != "approved"
        or not alternative
    ):
        return failure(
            "alternative_not_approved",
            "Alternative checkout was blocked because explicit approval is missing.",
        )

    product_id = alternative.get("id")

    if not product_id:
        return failure(
            "invalid_alternative",
            "The approved alternative has no product ID.",
        )

    budget_ceiling = state.get("budget_ceiling")
    price = float(alternative.get("price") or 0)

    if budget_ceiling is not None and price > float(budget_ceiling):
        return failure(
            "budget_exceeded",
            "The approved alternative exceeds the user's budget.",
        )

    # Revalidate inventory because stock may have changed while
    # the graph was waiting for the user's decision.
    try:
        inventory = await check_inventory(str(product_id))
    except Exception as exc:
        return failure(
            "inventory_check_failed",
            f"Could not revalidate alternative inventory: {exc}",
        )

    if (
        inventory.get("error")
        or not inventory.get("in_stock")
        or int(inventory.get("stock_qty", 0)) < 1
    ):
        return failure(
            "alternative_out_of_stock",
            "The approved alternative is no longer available.",
        )

    # Exactly one order attempt for the explicitly approved alternative.
    try:
        arguments = {"items": [{"product_id": str(product_id), "quantity": 1}]}
        if state.get("thread_id"):
            arguments["graph_thread_id"] = state["thread_id"]
        result = await create_order(**arguments)
    except Exception as exc:
        return failure(
            "alternative_order_error",
            f"Alternative order creation raised an exception: {exc}",
        )

    if not result.get("created"):
        return failure(
            "alternative_order_failed",
            result.get("reason", "Alternative order creation failed."),
        )

    order_id = result.get("order_id")

    entry = DecisionLogEntry(
        step="checkout_alternative",
        decision="Approved alternative order created",
        reason=(
            f"Created order {order_id} for "
            f"{alternative.get('name')} after user approval."
        ),
        tokens_used=0,
        latency_ms=int((time.perf_counter() - started_at) * 1000),
    )

    return {
        "chosen_product": {
            **alternative,
            "stock_qty": int(inventory["stock_qty"]),
        },
        "order_status": "created",
        "order_id": order_id,
        "payment_status": "pending",
        "payment_details": {
            "order_id": order_id,
            "razorpay_order_id": result.get("razorpay_order_id"),
            "amount": result.get("total_amount"),
            "amount_paise": result.get("razorpay_amount"),
            "currency": result.get("currency", "INR"),
            "key_id": result.get("razorpay_key_id"),
            "items": result.get("cart", []),
        },
        "failure_reason": None,
        "decision_log": [*decision_log, entry],
    }
