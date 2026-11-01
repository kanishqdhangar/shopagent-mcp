from services.negotiation import parse_negotiation_message


def test_parses_discount_percent_and_best_price():
    assert parse_negotiation_message("Give me 10% off")["requested_discount_percent"] == 10
    assert parse_negotiation_message("Give me your best price")["action"] == "request_best"


def test_parses_absolute_price_and_limit_is_left_to_seller():
    result = parse_negotiation_message("I can buy it for ₹2,000")
    assert result == {"action": "request_target_price", "target_price": 2000.0}


def test_shopping_budget_is_not_mistaken_for_a_target_price():
    message = "Find running shoes under ₹3000. Also suggest running socks and offer me a discount if possible."
    assert parse_negotiation_message(message) == {"action": "request_best"}
    assert parse_negotiation_message("Find running shoes under ₹3000") is None


def test_pending_offer_accept_reject_and_cancel():
    assert parse_negotiation_message("I accept", pending_offer=True)["action"] == "accept"
    assert parse_negotiation_message("Buy it", pending_offer=True)["purchase_authorized"] is True
    assert parse_negotiation_message("No thanks", pending_offer=True)["action"] == "reject"
    assert parse_negotiation_message("Cancel the negotiation", pending_offer=True)["action"] == "cancel"


def test_unrelated_text_is_not_a_negotiation_action():
    assert parse_negotiation_message("Show me another product") is None
