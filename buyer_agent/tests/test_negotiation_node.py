import asyncio

from nodes import negotiate as negotiate_module


def make_state(action, pending=None, history=None):
    return {
        "run_id": "8d01ec22-98e4-440e-9c1c-0712e2817d4e",
        "thread_id": "session-a",
        "chosen_product": {"id": "product-a", "name": "Running shoes", "price": 2500},
        "negotiation_action": action,
        "pending_negotiation": pending,
        "negotiation_history": history or [],
        "negotiation_attempts": 0,
        "decision_log": [],
        "negotiation_status": "pending" if pending else "none",
    }


async def no_audit(**_kwargs):
    return None


def test_counteroffer_uses_seller_quote_and_keeps_history(monkeypatch):
    calls = []
    async def quote(**kwargs):
        calls.append(kwargs)
        return {"applied": True, "product_id": "product-a", "original_price": 2500.0,
                "requested_discount_percent": 10.0, "applied_discount_percent": 10.0,
                "discounted_price": 2250.0, "maximum_discount_percent": 15.0}
    monkeypatch.setattr(negotiate_module, "apply_discount", quote)
    monkeypatch.setattr(negotiate_module, "write_audit_log", no_audit)

    state = make_state({"action": "request_percent", "requested_discount_percent": 10},
                       pending={"product_id": "product-a", "original_price": 2500.0},
                       history=[{"status": "pending", "discount_percent": 5}])
    result = asyncio.run(negotiate_module.negotiate(state))
    assert calls[0]["percent"] == 10
    assert calls[0]["expected_original_price"] == 2500.0
    assert result["pending_negotiation"]["discounted_price"] == 2250.0
    assert len(result["negotiation_history"]) == 2


def test_accept_only_records_acceptance_without_checkout(monkeypatch):
    async def unexpected_quote(**_kwargs):
        raise AssertionError("Acceptance should not create or re-quote an order")
    monkeypatch.setattr(negotiate_module, "apply_discount", unexpected_quote)
    monkeypatch.setattr(negotiate_module, "write_audit_log", no_audit)
    pending = {"product_id": "product-a", "original_price": 2500.0,
               "discount_percent": 10.0, "discounted_price": 2250.0, "status": "pending"}

    accepted = asyncio.run(negotiate_module.negotiate(make_state({"action": "accept"}, pending=pending)))
    assert accepted["negotiation_status"] == "accepted"
    assert accepted["request_kind"] == "negotiation_complete"
    assert accepted["pending_negotiation"]["status"] == "accepted"


def test_request_above_limit_displays_only_seller_best_allowed_offer(monkeypatch):
    async def quote(**_kwargs):
        return {"applied": False, "product_id": "product-a", "original_price": 2500.0,
                "requested_discount_percent": 25.0, "applied_discount_percent": 0.0,
                "discounted_price": 2500.0, "maximum_discount_percent": 15.0,
                "rejection_reason": "Maximum is 15%.",
                "best_allowed_offer": {"discount_percent": 15.0, "discounted_price": 2125.0}}
    monkeypatch.setattr(negotiate_module, "apply_discount", quote)
    monkeypatch.setattr(negotiate_module, "write_audit_log", no_audit)

    result = asyncio.run(negotiate_module.negotiate(make_state({"action": "request_percent", "requested_discount_percent": 25})))
    assert result["negotiation_status"] == "maximum_reached"
    assert result["pending_negotiation"]["discount_percent"] == 15.0
    assert result["pending_negotiation"]["discounted_price"] == 2125.0
