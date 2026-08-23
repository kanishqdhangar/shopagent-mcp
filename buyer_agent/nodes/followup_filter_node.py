import re
from typing import Any

from langchain_core.messages import SystemMessage


def filter_previous_products(
    products: list[dict[str, Any]],
    message: str,
    active_filters: dict[str, Any],
) -> list[dict[str, Any]]:
    text = message.lower()

    filtered = products

    # ---------------------------------------------------------
    # Preserve original search constraints
    # ---------------------------------------------------------

    max_price = active_filters.get("max_price")

    if max_price is not None:
        filtered = [
            product
            for product in filtered
            if float(product.get("price", 0)) <= float(max_price)
        ]

    if active_filters.get("require_in_stock"):
        filtered = [
            product
            for product in filtered
            if int(product.get("stock_qty", 0)) > 0
        ]

    original_query = str(
        active_filters.get("query", "")
    ).lower()

    # If the original query was about running shoes,
    # don't allow unrelated products such as running T-shirts.
    if "running" in original_query and "shoe" in original_query:
        filtered = [
            product
            for product in filtered
            if (
                str(product.get("category", "")).lower() == "running"
                and str(product.get("subtype", "")).lower() == "shoes"
            )
        ]

    # ---------------------------------------------------------
    # Cheaper / cheapest
    # ---------------------------------------------------------

    if "cheapest" in text:
        if filtered:
            cheapest_price = min(
                float(product.get("price", 0))
                for product in filtered
            )

            filtered = [
                product
                for product in filtered
                if float(product.get("price", 0)) == cheapest_price
            ]

    elif "cheaper" in text:
        if filtered:
            prices = sorted(
                float(product.get("price", 0))
                for product in filtered
            )

            if len(prices) > 1:
                # Return the lower-priced half.
                cutoff_index = max(1, len(prices) // 2)
                cutoff_price = prices[cutoff_index - 1]

                filtered = [
                    product
                    for product in filtered
                    if float(product.get("price", 0)) <= cutoff_price
                ]

    # ---------------------------------------------------------
    # More expensive
    # ---------------------------------------------------------

    elif "more expensive" in text:
        if filtered:
            most_expensive_price = max(
                float(product.get("price", 0))
                for product in filtered
            )

            filtered = [
                product
                for product in filtered
                if float(product.get("price", 0))
                == most_expensive_price
            ]

    # ---------------------------------------------------------
    # Color
    # ---------------------------------------------------------

    color_match = re.search(
        r"\b(black|white|grey|gray|blue|red|green)\b",
        text,
    )

    if color_match:
        requested_color = color_match.group(1)

        if requested_color == "gray":
            requested_color = "grey"

        filtered = [
            product
            for product in filtered
            if str(
                (product.get("spec_json") or {}).get("color", "")
            ).lower() == requested_color
        ]

    # ---------------------------------------------------------
    # Size
    # ---------------------------------------------------------

    size_match = re.search(
        r"\buk\s*(\d+(?:\.\d+)?)\b",
        text,
    )

    if size_match:
        requested_size = f"UK {size_match.group(1)}"

        filtered = [
            product
            for product in filtered
            if str(product.get("size", "")).lower()
            == requested_size.lower()
        ]

    # ---------------------------------------------------------
    # Maximum price from follow-up
    # ---------------------------------------------------------

    price_match = re.search(
        r"(?:under|below|less than|up to)\s*[₹]?\s*([\d,]+)",
        text,
    )

    if price_match:
        max_price = float(
            price_match.group(1).replace(",", "")
        )

        filtered = [
            product
            for product in filtered
            if float(product.get("price", 0)) <= max_price
        ]

    # ---------------------------------------------------------
    # Minimum price from follow-up
    # ---------------------------------------------------------

    min_price_match = re.search(
        r"(?:above|over|more than)\s*[₹]?\s*([\d,]+)",
        text,
    )

    if min_price_match:
        min_price = float(
            min_price_match.group(1).replace(",", "")
        )

        filtered = [
            product
            for product in filtered
            if float(product.get("price", 0)) >= min_price
        ]

    # ---------------------------------------------------------
    # In-stock requirement
    # ---------------------------------------------------------

    if any(
        phrase in text
        for phrase in [
            "in stock",
            "available",
            "currently available",
        ]
    ):
        filtered = [
            product
            for product in filtered
            if int(product.get("stock_qty", 0)) > 0
        ]

    return filtered


def followup_filter_node(state):
    products = state.get("products", [])
    active_filters = state.get("active_filters", {})

    if not products:
        return {
            "products": [],
        }

    user_message = ""

    for message in reversed(state["messages"]):
        if getattr(message, "type", None) == "human":
            user_message = message.content
            break

    print("\n=== FOLLOWUP FILTER BEFORE ===")
    print("USER:", user_message)
    print("PRODUCT COUNT:", len(products))
    print("PRODUCTS:", [p.get("name") for p in products])
    print("ACTIVE FILTERS:", active_filters)

    filtered = filter_previous_products(
        products,
        user_message,
        active_filters,
    )

    print("\n=== FOLLOWUP FILTER AFTER ===")
    print("PRODUCT COUNT:", len(filtered))
    print("PRODUCTS:", [p.get("name") for p in filtered])
    print("==========================\n")

    return {
        "products": filtered,
        "active_filters": state.get("active_filters", {}),
        "messages": [
            SystemMessage(
                content=(
                    "The user's latest request was handled by filtering "
                    "the previously retrieved products. Do not call "
                    "search_catalog for this request. Answer using ONLY "
                    "the filtered products currently in state."
                )
            )
        ],
    }