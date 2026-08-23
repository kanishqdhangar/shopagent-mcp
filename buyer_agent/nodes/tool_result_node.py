from typing import Any


def extract_products(state) -> dict[str, Any]:
    products = []

    for message in state["messages"]:
        if message.type != "tool":
            continue

        if message.name != "search_catalog":
            continue

        try:
            data = message.content

            if isinstance(data, str):
                import json

                data = json.loads(data)

            products.extend(
                data.get("results", [])
            )

        except (ValueError, TypeError):
            continue

    return {
        "products": products
    }