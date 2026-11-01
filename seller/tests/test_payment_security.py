import hashlib
import hmac

from app.payment_security import verify_razorpay_signature
from app.payment_security import validate_payment_event
from decimal import Decimal


def test_razorpay_signature_uses_raw_body():
    body = b'{"event":"payment.captured"}'
    secret = "test-webhook-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(body, signature, secret)
    assert not verify_razorpay_signature(body + b" ", signature, secret)


def test_razorpay_signature_rejects_missing_values():
    assert not verify_razorpay_signature(b"body", "", "secret")
    assert not verify_razorpay_signature(b"body", "signature", "")


def test_payment_event_amount_and_currency_validation():
    expected = {"expected_amount": Decimal("25.00"), "expected_currency": "INR", "amount": 2500, "currency": "INR", "event_type": "payment.captured", "captured": True}
    assert validate_payment_event(**expected) is None
    assert "amount" in validate_payment_event(**{**expected, "amount": 2499})
    assert "currency" in validate_payment_event(**{**expected, "currency": "USD"})
    assert "captured" in validate_payment_event(**{**expected, "captured": False})
