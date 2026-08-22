from app.models import Product


def product_to_embedding_text(product: Product) -> str:
    parts = [
        f"Product: {product.name}",
        f"Category: {product.category}",
    ]

    if product.subtype:
        parts.append(f"Type: {product.subtype}")

    if product.description:
        parts.append(
            f"Description: {product.description.rstrip('.')}"
        )

    if product.size:
        parts.append(f"Size: {product.size}")

    if product.spec_json:
        specifications = ", ".join(
            f"{key}: {value}"
            for key, value in product.spec_json.items()
        )

        parts.append(
            f"Specifications: {specifications}"
        )

    return ". ".join(parts)