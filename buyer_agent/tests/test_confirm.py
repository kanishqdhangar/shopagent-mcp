
import pytest
from unittest.mock import AsyncMock

import nodes.confirm as confirm_module


@pytest.fixture
def payment_state():
    return {
        "order_id": "order-123",
        "decision_log": [],
    }


@pytest.mark.asyncio
async def test_payment_already_paid(monkeypatch, payment_state):
    mock_status = AsyncMock(return_value={"status": "paid"})
    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)

    result = await confirm_module.confirm(payment_state)

    mock_status.assert_awaited_once_with(order_id="order-123")
    assert result["order_status"] == "paid"
    assert result["failure_reason"] is None


@pytest.mark.asyncio
async def test_payment_becomes_paid_after_pending(monkeypatch, payment_state):
    mock_status = AsyncMock(side_effect=[
        {"status": "pending"},
        {"status": "created"},
        {"status": "paid"},
    ])
    mock_sleep = AsyncMock()

    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)
    monkeypatch.setattr(confirm_module.asyncio, "sleep", mock_sleep)

    result = await confirm_module.confirm(payment_state)

    assert mock_status.await_count == 3
    assert mock_sleep.await_count == 2
    assert result["order_status"] == "paid"
    assert result["failure_reason"] is None


@pytest.mark.asyncio
async def test_payment_remains_pending_after_max_attempts(
    monkeypatch, payment_state
):
    mock_status = AsyncMock(return_value={"status": "pending"})
    mock_sleep = AsyncMock()

    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)
    monkeypatch.setattr(confirm_module.asyncio, "sleep", mock_sleep)

    result = await confirm_module.confirm(payment_state)

    assert mock_status.await_count == confirm_module.MAX_ATTEMPTS
    assert mock_sleep.await_count == confirm_module.MAX_ATTEMPTS - 1
    assert result["order_status"] == "payment_pending"
    assert result["failure_reason"] == "payment_confirmation_timeout"


@pytest.mark.asyncio
async def test_missing_order_id_does_not_call_status_service(
    monkeypatch,
):
    state = {"order_id": None, "decision_log": []}
    mock_status = AsyncMock()

    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)

    result = await confirm_module.confirm(state)

    mock_status.assert_not_awaited()
    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "missing_order_id"


@pytest.mark.asyncio
async def test_order_status_service_returns_error(monkeypatch, payment_state):
    mock_status = AsyncMock(return_value={
        "error": "Order not found",
    })

    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)

    result = await confirm_module.confirm(payment_state)

    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "order_not_found"


@pytest.mark.asyncio
async def test_order_status_service_raises_exception(
    monkeypatch, payment_state
):
    mock_status = AsyncMock(
        side_effect=Exception("Database unavailable")
    )

    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)

    result = await confirm_module.confirm(payment_state)

    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "order_status_error"


@pytest.mark.asyncio
async def test_unexpected_payment_status(monkeypatch, payment_state):
    mock_status = AsyncMock(return_value={"status": "cancelled"})

    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)

    result = await confirm_module.confirm(payment_state)

    assert result["order_status"] == "failed"
    assert result["failure_reason"] == "payment_failed"


@pytest.mark.asyncio
async def test_created_status_continues_polling(monkeypatch, payment_state):
    mock_status = AsyncMock(side_effect=[
        {"status": "created"},
        {"status": "paid"},
    ])
    mock_sleep = AsyncMock()

    monkeypatch.setattr(confirm_module, "get_order_status", mock_status)
    monkeypatch.setattr(confirm_module.asyncio, "sleep", mock_sleep)

    result = await confirm_module.confirm(payment_state)

    assert mock_status.await_count == 2
    assert mock_sleep.await_count == 1
    assert result["order_status"] == "paid"
