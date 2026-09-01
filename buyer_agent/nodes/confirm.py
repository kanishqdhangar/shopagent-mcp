import asyncio
import time
from typing import Any

from state import AgentState, DecisionLogEntry
from tools.mcp_tools import get_order_status


MAX_ATTEMPTS = 6
POLL_INTERVAL_SECONDS = 2


async def confirm(state: AgentState) -> dict[str, Any]:
    started_at = time.perf_counter()

    order_id = state.get("order_id")

    if not order_id:
        latency_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        log_entry = DecisionLogEntry(
            step="confirm",
            decision="Payment confirmation failed",
            reason="No order ID is available.",
            tokens_used=0,
            latency_ms=latency_ms,
        )

        return {
            "order_status": "failed",
            "failure_reason": "missing_order_id",
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = await get_order_status(
                order_id=order_id,
            )
        except Exception as exc:
            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            log_entry = DecisionLogEntry(
                step="confirm",
                decision="Payment confirmation failed",
                reason=(
                    f"Unable to retrieve order status: {exc}"
                ),
                tokens_used=0,
                latency_ms=latency_ms,
            )

            return {
                "order_status": "failed",
                "failure_reason": "order_status_error",
                "decision_log": [
                    *state["decision_log"],
                    log_entry,
                ],
            }

        if result.get("error"):
            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            reason = result.get(
                "error",
                "Order status lookup failed.",
            )

            log_entry = DecisionLogEntry(
                step="confirm",
                decision="Payment confirmation failed",
                reason=reason,
                tokens_used=0,
                latency_ms=latency_ms,
            )

            return {
                "order_status": "failed",
                "failure_reason": "order_not_found",
                "decision_log": [
                    *state["decision_log"],
                    log_entry,
                ],
            }

        status = result.get("status")

        if status == "paid":
            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            log_entry = DecisionLogEntry(
                step="confirm",
                decision="Payment confirmed",
                reason=(
                    f"Order {order_id} has been marked as paid."
                ),
                tokens_used=0,
                latency_ms=latency_ms,
            )

            return {
                "order_status": "paid",
                "failure_reason": None,
                "decision_log": [
                    *state["decision_log"],
                    log_entry,
                ],
            }

        if status not in {"created", "pending"}:
            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            log_entry = DecisionLogEntry(
                step="confirm",
                decision="Payment confirmation failed",
                reason=(
                    f"Order {order_id} has unexpected "
                    f"status '{status}'."
                ),
                tokens_used=0,
                latency_ms=latency_ms,
            )

            return {
                "order_status": "failed",
                "failure_reason": "payment_failed",
                "decision_log": [
                    *state["decision_log"],
                    log_entry,
                ],
            }

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(
                POLL_INTERVAL_SECONDS
            )

    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    log_entry = DecisionLogEntry(
        step="confirm",
        decision="Payment confirmation pending",
        reason=(
            f"Order {order_id} was not marked as paid "
            f"after {MAX_ATTEMPTS} status checks."
        ),
        tokens_used=0,
        latency_ms=latency_ms,
    )

    return {
        "order_status": "payment_pending",
        "failure_reason": "payment_confirmation_timeout",
        "decision_log": [
            *state["decision_log"],
            log_entry,
        ],
    }