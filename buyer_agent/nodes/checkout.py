import time
from typing import Any

from state import AgentState, DecisionLogEntry
from tools.mcp_tools import create_order


async def checkout(state: AgentState) -> dict[str, Any]:
    started_at = time.perf_counter()

    chosen_product = state.get("chosen_product")

    if not chosen_product:
        latency_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        log_entry = DecisionLogEntry(
            step="checkout",
            decision="Checkout failed",
            reason="No product was selected.",
            tokens_used=0,
            latency_ms=latency_ms,
        )

        return {
            "order_status": "failed",
            "failure_reason": "no_product_selected",
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    product_id = chosen_product.get("id")

    if not product_id:
        latency_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        log_entry = DecisionLogEntry(
            step="checkout",
            decision="Checkout failed",
            reason="Selected product is missing an ID.",
            tokens_used=0,
            latency_ms=latency_ms,
        )

        return {
            "order_status": "failed",
            "failure_reason": "invalid_product",
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    items = [
        {
            "product_id": str(product_id),
            "quantity": 1,
        }
    ]

    try:
        result = await create_order(
            items=items,
        )

    except Exception as exc:
        latency_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        log_entry = DecisionLogEntry(
            step="checkout",
            decision="Checkout failed",
            reason=f"Order creation raised an exception: {exc}",
            tokens_used=0,
            latency_ms=latency_ms,
        )

        return {
            "order_status": "failed",
            "failure_reason": "order_creation_error",
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    if not result.get("created"):
        reason = result.get(
            "reason",
            "Order creation failed.",
        )

        log_entry = DecisionLogEntry(
            step="checkout",
            decision="Checkout failed",
            reason=reason,
            tokens_used=0,
            latency_ms=latency_ms,
        )

        return {
            "order_status": "failed",
            "failure_reason": "order_creation_failed",
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    order_id = result.get("order_id")

    log_entry = DecisionLogEntry(
        step="checkout",
        decision="Order created",
        reason=(
            f"Created order {order_id} for "
            f"{chosen_product.get('name')}."
        ),
        tokens_used=0,
        latency_ms=latency_ms,
    )

    return {
        "order_status": "created",
        "order_id": order_id,
        "failure_reason": None,
        "decision_log": [
            *state["decision_log"],
            log_entry,
        ],
    }