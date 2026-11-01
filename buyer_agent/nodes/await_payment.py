from typing import Any

from langgraph.types import interrupt

from state import AgentState, DecisionLogEntry


async def await_payment(state: AgentState) -> dict[str, Any]:
    details = state.get("payment_details") or {}
    outcome = interrupt({
        "type": "payment_required",
        "message": "Complete payment to continue with this order.",
        "payment": details,
    })
    payment_status = outcome.get("payment_status") if isinstance(outcome, dict) else None
    if payment_status == "paid":
        return {"payment_status": "paid", "order_status": "paid", "failure_reason": None}
    return {"payment_status": "failed", "order_status": "failed", "failure_reason": "payment_failed"}


async def handle_payment_failure(state: AgentState) -> dict[str, Any]:
    entry = DecisionLogEntry(
        step="payment_failure",
        decision="Payment failed",
        reason=f"The seller confirmed that payment for order {state.get('order_id')} failed.",
        tokens_used=0,
        latency_ms=0,
    )
    return {
        "payment_status": "failed",
        "order_status": "failed",
        "failure_reason": "payment_failed",
        "decision_log": [*state.get("decision_log", []), entry],
    }
