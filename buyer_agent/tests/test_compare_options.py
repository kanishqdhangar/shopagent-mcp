
import asyncio
import json

from nodes.compare_options import compare_options
from tools.mcp_tools import find_products_by_name


async def main():
    # Retrieve actual products from the seller MCP server.
    result = await find_products_by_name([
        "AeroRun Lite Trainers",
        "ComfortRun Daily Shoes",
    ])

    candidates = result.get("results", [])

    assert len(candidates) == 2, (
        f"Expected 2 products, received {len(candidates)}"
    )

    state = {
        "goal": (
            "Compare AeroRun Lite Trainers and ComfortRun Daily Shoes "
            "and choose whichever provides better value for money."
        ),
        "scenario": "restock_or_compare",
        "parsed_filters": {
            "intent_type": "compare",
            "product_names": [
                "AeroRun Lite Trainers",
                "ComfortRun Daily Shoes",
            ],
        },
        "candidates": candidates,
        "chosen_product": None,
        "upsell_offer": None,
        "confidence": 0.0,
        "retry_count": 0,
        "budget_ceiling": 3000.0,
        "order_status": "not_started",
        "order_id": None,
        "decision_log": [],
        "failure_reason": None,
    }

    output = await compare_options(state)

    print("\n--- COMPARISON RESULT ---")
    print(json.dumps({
        "chosen_product": output["chosen_product"],
        "confidence": output["confidence"],
        "decision_log": [
            entry.model_dump()
            if hasattr(entry, "model_dump")
            else entry
            for entry in output["decision_log"]
        ],
        "failure_reason": output.get("failure_reason"),
    }, indent=2, default=str))

    assert output["chosen_product"] is not None, (
        "Comparison did not select a valid product."
    )

    assert output["chosen_product"]["id"] in {
        product["id"] for product in candidates
    }, "Selected product is not in the candidate list."

    assert len(output["decision_log"]) == 1, (
        "Expected one comparison audit entry."
    )

    print("\nPASS: Comparison node selected a valid catalog product.")


if __name__ == "__main__":
    asyncio.run(main())
