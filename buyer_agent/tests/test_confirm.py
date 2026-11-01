import pytest

from nodes.confirm import confirm


@pytest.mark.asyncio
async def test_confirm_completes_only_after_trusted_payment_resume():
    result = await confirm({"order_id": "order-123", "payment_status": "paid", "decision_log": []})
    assert result["order_status"] == "paid"
    assert result["failure_reason"] is None
    assert result["decision_log"][0].decision == "Payment confirmed"


@pytest.mark.asyncio
async def test_confirm_does_not_mark_order_paid_without_payment_event():
    result = await confirm({"order_id": "order-123", "payment_status": "pending", "decision_log": []})
    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "payment_not_confirmed"
