import asyncio

import graph
from state import DecisionLogEntry


attempts = 0


async def fake_parse_intent(state):
    global attempts
    attempts += 1

    return {
        "retry_count": state.get("retry_count", 0) + 1,
        "parsed_filters": {"intent_type": "search"},
        "budget_ceiling": 3000.0,
        "decision_log": [
            *state["decision_log"],
            DecisionLogEntry(
                step="parse_intent",
                decision=f"Mock parsing attempt {attempts}",
                reason="Controlled low-confidence test.",
                tokens_used=0,
                latency_ms=0,
            ),
        ],
    }


async def fake_rag_search(state):
    return {
        "candidates": [{"name": "Test Product", "price": 1000}],
        "decision_log": state["decision_log"],
    }


async def fake_compare_options(state):
    confidence_values = {
        1: 0.30,
        2: 0.35,
        3: 0.40,
    }

    confidence = confidence_values[attempts]

    return {
        "confidence": confidence,
        "chosen_product": None,
        "decision_log": [
            *state["decision_log"],
            DecisionLogEntry(
                step="compare_options",
                decision="Low confidence",
                reason=f"Mock confidence: {confidence}",
                tokens_used=0,
                latency_ms=0,
            ),
        ],
    }


async def should_not_checkout(state):
    raise AssertionError("Checkout must not execute!")


async def main():
    graph.parse_intent = fake_parse_intent
    graph.rag_search = fake_rag_search
    graph.compare_options = fake_compare_options
    graph.checkout = should_not_checkout

    app = await graph.build_buyer_graph()

    initial_state = {
        "goal": "Find a running shoe",
        "scenario": "search",
        "parsed_filters": None,
        "candidates": [],
        "chosen_product": None,
        "upsell_offer": None,
        "confidence": 0.0,
        "budget_ceiling": 3000.0,
        "order_status": "not_started",
        "order_id": None,
        "retry_count": 0,
        "decision_log": [],
        "failure_reason": None,
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "confidence-retry-test-v2"}},
    )

    print("\n=== CONFIDENCE RETRY TEST ===")
    print("Attempts:", attempts)
    print("Retry count:", result.get("retry_count"))
    print("Confidence:", result.get("confidence"))
    print("Failure:", result.get("failure_reason"))
    print("Order status:", result.get("order_status"))

    print("\nDECISION LOG:")
    for entry in result["decision_log"]:
        print(entry.step, "|", entry.decision, "|", entry.reason)

    assert attempts == 3
    assert result["retry_count"] == 3
    assert result["failure_reason"] == "low_confidence"
    assert result["order_status"] == "not_started"

    print("\nPASS: Confidence retry limit works correctly.")


if __name__ == "__main__":
    asyncio.run(main())