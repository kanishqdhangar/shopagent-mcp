import asyncio

from nodes.compare_options import compare_options


async def main():
    state = {
        "goal": "Find me a lightweight running shoe under ₹3000.",
        "scenario": "budget_search",
        "parsed_filters": {
            "intent_type": "search",
            "category": "running",
            "subtype": "shoes",
            "budget": 3000.0,
            "product_names": [],
            "search_query": "lightweight running shoes",
        },
        "candidates": [
            {
                "id": "eb5e2833-d31c-44d1-95b2-6ea108610b89",
                "name": "AeroRun Lite Trainers",
                "category": "running",
                "subtype": "shoes",
                "price": "2899.00",
                "size": "UK 8",
                "spec_json": {
                    "use": "Daily running",
                    "drop": "8mm",
                    "color": "White",
                    "material": "Engineered Mesh",
                    "cushioning": "Medium",
                },
                "stock_qty": 18,
                "description": (
                    "Lightweight and breathable trainers "
                    "designed for comfortable everyday runs."
                ),
            },
            {
                "id": "55b5168c-6364-40aa-b522-cb62ad2ae7a9",
                "name": "ComfortRun Daily Shoes",
                "category": "running",
                "subtype": "shoes",
                "price": "2499.00",
                "size": "UK 8",
                "spec_json": {
                    "use": "Daily running",
                    "drop": "10mm",
                    "color": "Grey",
                    "material": "Mesh",
                    "cushioning": "Soft",
                },
                "stock_qty": 21,
                "description": (
                    "Affordable cushioned running shoes "
                    "for comfortable daily jogging and "
                    "beginner runners."
                ),
            },
        ],
        "chosen_product": None,
        "upsell_offer": None,
        "budget_ceiling": 3000.0,
        "order_status": "not_started",
        "order_id": None,
        "decision_log": [],
        "failure_reason": None,
    }

    result = await compare_options(state)

    print("\nCHOSEN PRODUCT:")
    print(result["chosen_product"])

    print("\nDECISION LOG:")
    print(result["decision_log"][0].model_dump())


if __name__ == "__main__":
    asyncio.run(main())