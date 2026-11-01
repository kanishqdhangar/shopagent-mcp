import re
from typing import Any


_NUMBER = r"([0-9][0-9,]*(?:\.[0-9]+)?)"
_PERCENT = re.compile(_NUMBER + r"\s*(?:%|\bpercent(?:age)?\b)", re.IGNORECASE)
_CURRENCY = re.compile(r"(?:₹|\bINR\s*|\bRs\.?\s*)" + _NUMBER, re.IGNORECASE)


def parse_negotiation_message(message: str, pending_offer: bool = False) -> dict[str, Any] | None:
    """Recognize bargaining intent and numbers without generating prices."""
    text = message.strip()
    normalized = text.casefold()
    if not normalized:
        return None

    if re.search(r"\b(cancel|stop|end)\b.{0,24}\b(negotiat(?:e|ion)|offer|bargain)\b|\bcancel\s+it\b", normalized):
        return {"action": "cancel"}

    accepts = re.search(r"\b(accept|accepted|agree|agreed|deal|sounds good|go ahead)\b", normalized)
    purchase_directive = re.search(r"\b(buy|purchase|order)\s+(it|this|that|them)\b|\bgo ahead and buy\b", normalized)
    if pending_offer and (accepts or purchase_directive or normalized in {"yes", "yes please", "okay", "ok"}):
        return {"action": "accept", "purchase_authorized": bool(purchase_directive)}

    if pending_offer and re.search(r"\b(reject|no thanks|no,?\s+i|don.t want|do not want|decline)\b", normalized):
        return {"action": "reject"}

    percent_match = _PERCENT.search(text)
    if percent_match:
        try:
            percent = float(percent_match.group(1).replace(",", ""))
        except ValueError:
            return {"action": "invalid", "reason": "I couldn't read that discount percentage."}
        return {"action": "request_percent", "requested_discount_percent": percent}

    # A currency amount can be a shopping budget (e.g. "under ₹3,000"),
    # so only treat it as a counteroffer when the user explicitly proposes
    # the amount as the product's price.
    absolute_cue = re.search(
        r"\b(?:i can buy it for|i could buy it for|i would pay|i can pay|"
        r"make it|down to|price of|pay|buy it for|can you do|could you do)\b",
        normalized,
    )
    if absolute_cue:
        match = _CURRENCY.search(text) or re.search(
            r"\b(?:make it|down to|price of|pay|buy it for|can you do|could you do)\s*₹?\s*" + _NUMBER,
            text,
            re.IGNORECASE,
        )
        if match:
            group = match.group(1)
            try:
                target = float(group.replace(",", ""))
            except ValueError:
                return {"action": "invalid", "reason": "I couldn't read that target price."}
            return {"action": "request_target_price", "target_price": target}

    if re.search(r"\b(best price|best offer|best you can do|do better|too expensive|reduce|lower|discount|off)\b", normalized):
        return {"action": "request_best"}

    return None
