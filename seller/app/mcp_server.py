from mcp.server import MCPServer

from mcp.server.transport_security import TransportSecuritySettings

from app.db import AsyncSessionLocal
from app.schemas import ProductResponse
from app.services.embedding_service import embedding_service

from uuid import UUID

from app.services.product_service import (search_products, check_inventory as check_inventory_service,
    get_product as get_product_service)
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