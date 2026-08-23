from typing import Any


def filter_previous_products(
    products: list[dict[str, Any]],
    *,
    color: str | None = None,
    size: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    require_in_stock: bool | None = None,
) -> list[dict[str, Any]]:
    filtered = []

    for product in products:
        spec = product.get("spec_json") or {}

        if color:
            product_color = str(
                spec.get("color", "")
            ).lower()

            if product_color != color.lower():
                continue

        if size:
            if str(product.get("size", "")).lower() != size.lower():
                continue

        if max_price is not None:
            if float(product.get("price", 0)) > max_price:
                continue

        if min_price is not None:
            if float(product.get("price", 0)) < min_price:
                continue

        if require_in_stock:
            if int(product.get("stock_qty", 0)) <= 0:
                continue

        filtered.append(product)

    return filtered