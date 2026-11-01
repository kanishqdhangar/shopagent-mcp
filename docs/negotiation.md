# Conversational bargaining

ShopAgent supports conversational discounts for the product selected in a
shopping session. Bargaining uses the existing buyer-agent `/chat`
endpoint and the same `session_id`; there is no separate negotiation
endpoint.

## How an offer is calculated

The buyer agent recognizes a percentage request, a proposed target price,
or a request for the best price, then calls the seller MCP
`apply_discount` tool. The seller service reads the product's original
catalog price and calculates the quote with decimal arithmetic and
two-decimal rounding. The catalog price is never changed, so repeated
quotes do not compound.

The seller enforces `MAX_DISCOUNT_PERCENT`, which defaults to 15% in
`seller/app/config.py`. For a target price, the seller computes the
implied discount percentage and validates it against the same limit. A
request above the limit is rejected and may return the seller's maximum
allowed offer. The buyer agent does not calculate the final offer price.

## Chat flow

Start with a product request and a discount request, or select a product
first and negotiate in a later message. Example initial request:

```json
{
  "message": "Find running shoes and give me 10% off",
  "session_id": "shopper-session-123"
}
```

An offer response includes structured data for the UI:

```json
{
  "response": "The seller's configured discount policy offers 10.00% off Running shoes: ₹2,499.00 to ₹2,249.10. You can accept, counteroffer, or reject.",
  "session_id": "shopper-session-123",
  "negotiation": {
    "product_id": "<seller product UUID>",
    "product_name": "Running shoes",
    "original_price": 2499.0,
    "discount_percent": 10.0,
    "discounted_price": 2249.1,
    "status": "pending",
    "history": []
  }
}
```

Send each follow-up to `/chat` with the same `session_id`. For example,
to counteroffer:

```json
{
  "message": "Can you make it 12%?",
  "session_id": "shopper-session-123"
}
```

The shopper can also propose a price, ask for the best price, reject the
offer, or cancel the negotiation. The response's `negotiation.status`
describes the offer state, and `negotiation.history` contains the prior
offer decisions.

## Acceptance and checkout

Accepting an offer records acceptance; it does not create an order. Send
a separate, explicit purchase message after acceptance, for example:

```json
{
  "message": "Buy it",
  "session_id": "shopper-session-123"
}
```

Before checkout, the buyer agent asks the seller to revalidate the
accepted discount and the original catalog price. The seller's
`create_order` service checks the discount limit and expected catalog
price again, calculates the cart line total from the original price and
discount percentage, and uses that final total to create the Razorpay
order. The original catalog price remains unchanged.

The deterministic budget guardrail uses an accepted negotiation price
for the selected product. A discount is tied to that product and is not
transferred to a different product offered after a stock failure.

## Scope

Conversational negotiation is distinct from `check_upsell`. The current
upsell node selects from existing search candidates; it does not search
for complementary products or request/apply a discounted upsell. The
budget guardrail does not add a complementary upsell price to the
selected product's total.
