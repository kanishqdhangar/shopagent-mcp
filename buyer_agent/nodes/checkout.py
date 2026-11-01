
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

    budget_ceiling = state.get("budget_ceiling")
    offer = state.get("pending_negotiation") or {}
    accepted_offer = (
        state.get("negotiation_status") == "accepted"
        and offer.get("status") == "accepted"
        and offer.get("product_id") == str(chosen_product.get("id"))
    )

    async def attempt_order(product):
        arguments = {"items": [{"product_id": str(product["id"]), "quantity": 1}]}
        if accepted_offer and str(product.get("id")) == offer.get("product_id"):
            arguments["items"][0].update({
                "discount_percent": offer.get("discount_percent"),
                "expected_original_price": offer.get("original_price"),
            })
        if state.get("thread_id"):
            arguments["graph_thread_id"] = state["thread_id"]
        return await create_order(**arguments)

    # Attempt 1: Original selected product.
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
                f"{chosen_product.get('name')}" + (f" with seller-validated {offer.get('discount_percent')}% discount." if accepted_offer else ".")
            ),
            tokens_used=0,
            latency_ms=latency(),
        )

        return {
            "chosen_product": chosen_product,
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
            "confirmation_status": "not_required",
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
                f"{chosen_product.get('name')} is unavailable. "
                "Searching for an in-stock alternative."
            ),
            tokens_used=0,
            latency_ms=latency(),
        )
    )

    # Find an alternative, but DO NOT order it yet.
    candidates = state.get("candidates", [])
    alternative = None

    for candidate in candidates:
        candidate_id = candidate.get("id")

        if not candidate_id:
            continue

        if str(candidate_id) == str(product_id):
            continue

        price = float(candidate.get("price") or 0)

        if budget_ceiling is not None and price > float(budget_ceiling):
            continue
        
        try:
            inventory = await check_inventory(str(candidate_id))
        except Exception:
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
            decision="Alternative awaiting user confirmation",
            reason=(
                f"{alternative.get('name')} is available at "
                f"₹{float(alternative.get('price') or 0):,.2f}. "
                "No alternative order was created. "
                "Waiting for explicit user approval."
            ),
            tokens_used=0,
            latency_ms=latency(),
        )
    )

    return {
        "pending_alternative": alternative,
        "alternative_approved": False,
        "confirmation_status": "pending",
        "order_status": "awaiting_confirmation",
        "order_id": None,
        "failure_reason": None,
        "decision_log": decision_log,
    }
