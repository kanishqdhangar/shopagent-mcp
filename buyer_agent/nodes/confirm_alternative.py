
from langgraph.types import interrupt

from state import AgentState, DecisionLogEntry


async def confirm_alternative(state: AgentState) -> dict:
    alternative = state.get("pending_alternative")

    if not alternative:
        return {
            "alternative_approved": False,
            "confirmation_status": "rejected",
            "order_status": "cancelled",
            "failure_reason": "no_pending_alternative",
        }

    # Execution pauses here until the API resumes this graph thread.
    # No order or payment operation occurs in this node.
    decision = interrupt({
        "type": "alternative_confirmation_required",
        "message": (
            "Your requested product is unavailable. "
            "Would you like to purchase this alternative instead?"
        ),
        "product": {
            "id": alternative["id"],
            "name": alternative["name"],
            "price": float(alternative["price"]),
            "stock_qty": alternative["stock_qty"],
            "description": alternative.get("description", ""),
        },
    })

    # Only an explicit approval is accepted.
    approved = (
        isinstance(decision, dict)
        and decision.get("approved") is True
    )

    if approved:
        entry = DecisionLogEntry(
            step="confirm_alternative",
            decision="Alternative approved by user",
            reason=(
                f"User explicitly approved "
                f"{alternative['name']}."
            ),
            tokens_used=0,
            latency_ms=0,
        )

        return {
            "alternative_approved": True,
            "confirmation_status": "approved",
            "chosen_product": alternative,
            "decision_log": [
                *state.get("decision_log", []),
                entry,
            ],
        }

    entry = DecisionLogEntry(
        step="confirm_alternative",
        decision="Alternative rejected by user",
        reason=(
            f"User did not approve purchasing "
            f"{alternative['name']}."
        ),
        tokens_used=0,
        latency_ms=0,
    )

    return {
        "alternative_approved": False,
        "confirmation_status": "rejected",
        "order_status": "cancelled",
        "failure_reason": "alternative_rejected",
        "order_id": None,
        "decision_log": [
            *state.get("decision_log", []),
            entry,
        ],
    }
