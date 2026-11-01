
import pytest
from uuid import uuid4
import graph as graph_module
from state import DecisionLogEntry

thread_id = f"pytest-confidence-retry-{uuid4()}"

@pytest.mark.asyncio
async def test_low_confidence_retries_then_fails(monkeypatch):
    attempts = {"count": 0}

    async def fake_parse_intent(state):
        attempts["count"] += 1

        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "parsed_filters": {"intent_type": "search"},
            "budget_ceiling": 3000.0,
            "decision_log": state["decision_log"],
        }

    async def fake_rag_search(state):
        return {
            "candidates": [{"name": "Test Product", "price": 1000}],
            "decision_log": state["decision_log"],
        }

    async def fake_compare_options(state):
        confidence = {
            1: 0.30,
            2: 0.35,
            3: 0.40,
        }[attempts["count"]]

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
        pytest.fail("Checkout must not execute for low confidence.")

    monkeypatch.setattr(graph_module, "parse_intent", fake_parse_intent)
    monkeypatch.setattr(graph_module, "rag_search", fake_rag_search)
    monkeypatch.setattr(graph_module, "compare_options", fake_compare_options)
    monkeypatch.setattr(graph_module, "checkout", should_not_checkout)

    app = await graph_module.build_buyer_graph()

    try:
        result = await app.ainvoke(
            {
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
            },
            config={
                "configurable": {
                    "thread_id": thread_id,
                }
            },
        )

        assert attempts["count"] == 3
        assert result["retry_count"] == 3
        assert result["failure_reason"] == "low_confidence"
        assert result["order_status"] == "not_started"

    finally:
        await app.checkpointer.adelete_thread(thread_id)
