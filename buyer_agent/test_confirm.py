import asyncio

from nodes.confirm import confirm


async def main():
    state = {
        "goal": "Test payment confirmation",
        "scenario": "checkout",
        "parsed_filters": None,
        "candidates": [],
        "chosen_product": None,
        "confidence": 1.0,
        "upsell_offer": None,
        "budget_ceiling": 3000.0,
        "order_status": "created",

        # IMPORTANT:
        # Replace this with an actual order ID
        # that currently has status "created".
        "order_id": "a0330cdc-2e4d-4029-a3b8-beb093286188",

        "decision_log": [],
        "failure_reason": None,
    }

    result = await confirm(state)

    print("\n=== CONFIRM TEST ===")
    print("Order status:", result.get("order_status"))
    print("Failure reason:", result.get("failure_reason"))
    print("Decision log:")

    for entry in result.get("decision_log", []):
        print(entry)


if __name__ == "__main__":
    asyncio.run(main())