import time
from typing import Any

from state import AgentState, DecisionLogEntry


async def confirm(state: AgentState) -> dict[str, Any]:
    """Complete the purchase workflow after a trusted payment event resumes it."""
    started = time.perf_counter()
    if state.get("payment_status") != "paid":
        return {
            "order_status": "failed",
            "failure_reason": "payment_not_confirmed",
        }
    entry = DecisionLogEntry(
        step="confirm",
        decision="Payment confirmed",
        reason=f"Order {state.get('order_id')} was confirmed by the seller webhook.",
        tokens_used=0,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return {
        "order_status": "paid",
        "failure_reason": None,
        "decision_log": [*state.get("decision_log", []), entry],
    }
