from typing import Any


def filter_products(
    products: list[dict[str, Any]],
    max_price: float | None = None,
    require_in_stock: bool = False,
    category: str | None = None,
    subtype: str | None = None,
) -> list[dict[str, Any]]:
    """
    Apply deterministic business rules to catalog results.

    The LLM may identify user preferences, but this function
    enforces hard constraints.
    """

    filtered = []

    for result in products:
        product = result.get("product", {})

        price = float(product.get("price", 0))
        stock_qty = int(product.get("stock_qty", 0))

        if max_price is not None and price > max_price:
            continue

        if require_in_stock and stock_qty <= 0:
            continue

        if category is not None:
            product_category = str(
                product.get("category", "")
            ).lower()

            if product_category != category.lower():
                continue

        if subtype is not None:
            product_subtype = str(
                product.get("subtype", "")
            ).lower()

            if product_subtype != subtype.lower():
                continue

        filtered.append(result)

    return filtered