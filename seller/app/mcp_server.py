from mcp.server import MCPServer

from mcp.server.transport_security import TransportSecuritySettings

from app.db import AsyncSessionLocal
from app.schemas import ProductResponse
from app.services.embedding_service import embedding_service
from app.services.discount_service import apply_discount as apply_discount_service
from app.services.order_service import (
    create_order as create_order_service,
    get_order as get_order_service,
)
from uuid import UUID

from app.services.product_service import (search_products, check_inventory as check_inventory_service,
    get_product as get_product_service, find_products_by_name)
mcp = MCPServer(
    "ShopAgent Seller",
)


@mcp.tool()
async def search_catalog(
    query: str,
    limit: int = 5,
) -> dict:
    """
    Search the product catalog using semantic similarity.

    Args:
        query: Natural-language description of the products to find.
        limit: Maximum number of products to return.
    """

    if not query.strip():
        return {
            "query": query,
            "results": [],
        }

    limit = max(1, min(limit, 20))

    query_embedding = (
        await embedding_service.generate_embedding(
            query
        )
    )

    async with AsyncSessionLocal() as db:
        results = await search_products(
            db,
            query_embedding,
            limit,
        )

    return {
        "query": query,
        "results": [
            {
                "product": ProductResponse.model_validate(
                    product
                ).model_dump(mode="json"),
                "similarity": round(
                    1 - distance,
                    6,
                ),
            }
            for product, distance in results
        ],
    }

@mcp.tool()
async def get_product(
    product_id: str,
) -> dict:
    """
    Get detailed information about a single product.

    Args:
        product_id: UUID of the product.
    """

    try:
        parsed_product_id = UUID(product_id)
    except ValueError:
        return {
            "error": "Invalid product_id",
        }

    async with AsyncSessionLocal() as db:
        product = await get_product_service(
            db,
            parsed_product_id,
        )

    if product is None:
        return {
            "error": "Product not found",
            "product_id": product_id,
        }

    return {
        "product": ProductResponse.model_validate(
            product
        ).model_dump(mode="json")
    }

@mcp.tool()
async def find_products_by_name_tool(
    product_names: list[str],
) -> dict:
    """
    Find products by their exact names, including out-of-stock products.

    Args:
        product_names: List of product names to find.
    """

    async with AsyncSessionLocal() as db:
        products = await find_products_by_name(
            db,
            product_names,
        )

    return {
        "results": [
            ProductResponse.model_validate(product).model_dump(
                mode="json"
            )
            for product in products
        ]
    }

@mcp.tool()
async def check_inventory(
    product_id: str,
) -> dict:
    """
    Check the current inventory status of a product.

    Args:
        product_id: UUID of the product.
    """

    try:
        parsed_product_id = UUID(product_id)
    except ValueError:
        return {
            "error": "Invalid product_id",
        }

    async with AsyncSessionLocal() as db:
        product = await check_inventory_service(
            db,
            parsed_product_id,
        )

    if product is None:
        return {
            "error": "Product not found",
            "product_id": product_id,
        }

    return {
        "product_id": str(product.id),
        "stock_qty": product.stock_qty,
        "in_stock": product.stock_qty > 0,
    }

@mcp.tool()
async def apply_discount(
    product_id: str,
    percent: float,
) -> dict:
    """
    Apply a discount to a product price.

    Args:
        product_id: UUID of the product.
        percent: Discount percentage to apply.
    """

    try:
        parsed_product_id = UUID(product_id)
    except ValueError:
        return {
            "applied": False,
            "reason": "Invalid product_id.",
        }

    async with AsyncSessionLocal() as db:
        return await apply_discount_service(
            db,
            parsed_product_id,
            percent,
        )

@mcp.tool()
async def create_order(
    items: list[dict],
) -> dict:
    """
    Create an order after validating products and inventory.

    Args:
        items: List of cart items. Each item must contain
               product_id and quantity.
    """

    async with AsyncSessionLocal() as db:
        return await create_order_service(
            db,
            items,
        )

@mcp.tool()
async def get_order_status(
    order_id: str,
) -> dict:
    """
    Get the current status of a ShopAgent order.

    Args:
        order_id: ShopAgent order UUID.
    """

    try:
        parsed_order_id = UUID(order_id)
    except ValueError:
        return {
            "error": "Invalid order_id",
            "order_id": order_id,
        }

    async with AsyncSessionLocal() as db:
        order = await get_order_service(
            db,
            parsed_order_id,
        )

    if order is None:
        return {
            "error": "Order not found",
            "order_id": order_id,
        }

    return order