
from typing import Any

from state import AgentState, DecisionLogEntry


async def budget_guardrail(state: AgentState) -> dict[str, Any]:
    chosen_product = state.get("chosen_product")
    budget_ceiling = state.get("budget_ceiling")

    if not chosen_product:
        log_entry = DecisionLogEntry(
            step="budget_guardrail",
            decision="Budget check failed",
            reason="No product was selected.",
            tokens_used=0,
            latency_ms=0,
        )

        return {
            "failure_reason": "no_selected_product",
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    offer = state.get("pending_negotiation") or {}
    accepted_offer = (
        state.get("negotiation_status") == "accepted"
        and offer.get("status") == "accepted"
        and offer.get("product_id") == str(chosen_product.get("id"))
    )
    product_price = float(offer.get("discounted_price")) if accepted_offer else float(chosen_product.get("price", 0))

    # No explicit budget means there is no budget restriction.
    if budget_ceiling is None:
        log_entry = DecisionLogEntry(
            step="budget_guardrail",
            decision="Budget check passed",
            reason=(
                f"No explicit budget was provided. "
                f"Product price is ₹{product_price:.2f}; "
                "no budget restriction applies."
            ),
            tokens_used=0,
            latency_ms=0,
        )

        return {
            "failure_reason": None,
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    # Enforce the user's explicit budget deterministically.
    if product_price > float(budget_ceiling):
        log_entry = DecisionLogEntry(
            step="budget_guardrail",
            decision="Budget exceeded",
            reason=(
                f"Selected product costs ₹{product_price:.2f}, "
                f"which exceeds the budget ceiling of "
                f"₹{float(budget_ceiling):.2f}."
            ),
            tokens_used=0,
            latency_ms=0,
        )

        return {
            "failure_reason": "budget_exceeded",
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
        }

    log_entry = DecisionLogEntry(
        step="budget_guardrail",
        decision="Budget check passed",
        reason=(
            f"Selected product costs ₹{product_price:.2f}, "
            f"which is within the budget ceiling of "
            f"₹{float(budget_ceiling):.2f}."
        ),
        tokens_used=0,
        latency_ms=0,
    )

    return {
        "failure_reason": None,
        "decision_log": [
            *state["decision_log"],
            log_entry,
        ],
    }
