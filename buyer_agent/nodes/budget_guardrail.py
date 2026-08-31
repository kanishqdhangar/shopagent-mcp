from typing import Any

from state import AgentState, DecisionLogEntry


async def budget_guardrail(state: AgentState) -> dict[str, Any]:
    chosen_product = state.get("chosen_product")
    budget_ceiling = state.get("budget_ceiling", 0.0)

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

    product_price = float(chosen_product.get("price", 0))

    if product_price > budget_ceiling:
        log_entry = DecisionLogEntry(
            step="budget_guardrail",
            decision="Budget exceeded",
            reason=(
                f"Selected product costs ₹{product_price:.2f}, "
                f"which exceeds the budget ceiling of "
                f"₹{budget_ceiling:.2f}."
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
            f"₹{budget_ceiling:.2f}."
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