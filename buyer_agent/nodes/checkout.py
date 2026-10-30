
import time
from typing import Any

from state import AgentState, DecisionLogEntry
from tools.mcp_tools import create_order, check_inventory


async def checkout(state: AgentState) -> dict[str, Any]:
    started_at = time.perf_counter()

    chosen_product = state.get("chosen_product")
    decision_log = list(state.get("decision_log", []))

    def latency():
        return int((time.perf_counter() - started_at) * 1000)

    def failure(reason: str, message: str, product=None):
        entry = DecisionLogEntry(
            step="checkout",
            decision="Checkout failed",
            reason=message,
            tokens_used=0,
            latency_ms=latency(),
        )

        result = {
            "order_status": "failed",
            "failure_reason": reason,
            "order_id": None,
            "decision_log": [*decision_log, entry],
        }

        if product is not None:
            result["chosen_product"] = product

        return result

    if not chosen_product:
        return failure(
            "no_product_selected",
            "No product was selected.",
        )

    product_id = chosen_product.get("id")

    if not product_id:
        return failure(
            "invalid_product",
            "Selected product is missing an ID.",
        )

    budget_ceiling = float(state.get("budget_ceiling") or 0)

    async def attempt_order(product):
        return await create_order(
            items=[
                {
                    "product_id": str(product["id"]),
                    "quantity": 1,
                }
            ]
        )

    # Attempt 1: Create an order for the selected product.
    try:
        result = await attempt_order(chosen_product)
    except Exception as exc:
        return failure(
            "order_creation_error",
            f"Order creation raised an exception: {exc}",
        )

    if result.get("created"):
        order_id = result.get("order_id")

        entry = DecisionLogEntry(
            step="checkout",
            decision="Order created",
            reason=(
                f"Created order {order_id} for "
                f"{chosen_product.get('name')}."
            ),
            tokens_used=0,
            latency_ms=latency(),
        )

        return {
            "chosen_product": chosen_product,
            "order_status": "created",
            "order_id": order_id,
            "failure_reason": None,
            "decision_log": [*decision_log, entry],
        }

    # Do not retry unrelated failures.
    if result.get("error_code") != "INSUFFICIENT_STOCK":
        return failure(
            "order_creation_failed",
            result.get("reason", "Order creation failed."),
        )

    decision_log.append(
        DecisionLogEntry(
            step="checkout",
            decision="Stock failure detected",
            reason=(
                f"{chosen_product.get('name')} is no longer "
                "available in the requested quantity. "
                "Refreshing inventory and searching for an alternative."
            ),
            tokens_used=0,
            latency_ms=latency(),
        )
    )

    # Find an alternative from the already-filtered candidates.
    candidates = state.get("candidates", [])
    alternative = None

    for candidate in candidates:
        candidate_id = candidate.get("id")

        if not candidate_id:
            continue

        if str(candidate_id) == str(product_id):
            continue

        price = float(candidate.get("price") or 0)

        if budget_ceiling > 0 and price > budget_ceiling:
            continue

        try:
            inventory = await check_inventory(str(candidate_id))
        except Exception:
            # An inventory lookup failure must not trigger an
            # order attempt for an unverified candidate.
            continue

        if inventory.get("error"):
            continue

        stock_qty = int(inventory.get("stock_qty", 0))

        if inventory.get("in_stock") and stock_qty >= 1:
            alternative = {
                **candidate,
                "stock_qty": stock_qty,
            }
            break

    if alternative is None:
        return failure(
            "insufficient_stock_no_alternative",
            (
                "The selected product was out of stock and "
                "no eligible in-stock alternative was found."
            ),
        )

    decision_log.append(
        DecisionLogEntry(
            step="checkout",
            decision="Alternative product selected",
            reason=(
                f"Selected {alternative.get('name')} after "
                "refreshing its inventory."
            ),
            tokens_used=0,
            latency_ms=latency(),
        )
    )

    # Attempt 2: Exactly one retry with the alternative.
    try:
        retry_result = await attempt_order(alternative)
    except Exception as exc:
        return failure(
            "order_retry_error",
            f"Alternative order creation raised an exception: {exc}",
            product=alternative,
        )

    if not retry_result.get("created"):
        reason = retry_result.get(
            "reason",
            "Alternative order creation failed.",
        )

        failure_reason = (
            "insufficient_stock_after_retry"
            if retry_result.get("error_code") == "INSUFFICIENT_STOCK"
            else "order_retry_failed"
        )

        return failure(
            failure_reason,
            (
                "The single retry failed. "
                f"Seller response: {reason}"
            ),
            product=alternative,
        )

    order_id = retry_result.get("order_id")

    decision_log.append(
        DecisionLogEntry(
            step="checkout",
            decision="Order created after stock retry",
            reason=(
                f"Created order {order_id} for "
                f"{alternative.get('name')} after one retry."
            ),
            tokens_used=0,
            latency_ms=latency(),
        )
    )

    return {
        "chosen_product": alternative,
        "order_status": "created",
        "order_id": order_id,
        "failure_reason": None,
        "decision_log": decision_log,
    }
