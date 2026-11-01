import hashlib
import hmac
from decimal import Decimal


def verify_razorpay_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not raw_body or not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def validate_payment_event(
    *, expected_amount: Decimal, expected_currency: str, amount: int | None,
    currency: str | None, event_type: str, captured: bool,
) -> str | None:
    if amount is None or currency is None:
        return "Payment amount and currency are required."
    if int(expected_amount * 100) != amount:
        return "Payment amount does not match the order."
    if currency.upper() != expected_currency.upper():
        return "Payment currency does not match the order."
    if event_type in {"payment.captured", "order.paid"} and not captured:
        return "Payment is not captured."
    return None
