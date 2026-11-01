import json
from typing import Any

from langchain_core.tools import StructuredTool

from mcp_client import get_mcp_session

from services.product_filter import filter_products
from services.followup_filter import filter_previous_products

async def _call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    async with get_mcp_session() as session:
        result = await session.call_tool(
            tool_name,
            arguments,
        )

    if result.is_error:
        raise RuntimeError(
            f"MCP tool '{tool_name}' failed"
        )

    if not result.content:
        return {}

    text = result.content[0].text

    return json.loads(text)


async def search_catalog(
    query: str,
    limit: int = 5,
    max_price: float | None = None,
    require_in_stock: bool = False,
    category: str | None = None,
    subtype: str | None = None,
) -> dict[str, Any]:
    result = await _call_mcp_tool(
        "search_catalog",
        {
            "query": query,
            "limit": limit,
        },
    )

    filtered_results = filter_products(
        result.get("results", []),
        max_price=max_price,
        require_in_stock=require_in_stock,
        category=category,
        subtype=subtype,
    )

    return {
        "query": result.get("query", query),
        "results": filtered_results,
    }


async def find_products_by_name(
    product_names: list[str],
) -> dict[str, Any]:
    """
    Find products by exact names, including out-of-stock products.
    """
    return await _call_mcp_tool(
        "find_products_by_name_tool",
        {
            "product_names": product_names,
        },
    )

async def get_product(
    product_id: str,
) -> dict[str, Any]:
    return await _call_mcp_tool(
        "get_product",
        {
            "product_id": product_id,
        },
    )


async def check_inventory(
    product_id: str,
) -> dict[str, Any]:
    return await _call_mcp_tool(
        "check_inventory",
        {
            "product_id": product_id,
        },
    )

async def apply_discount(
    product_id: str,
    percent: float,
) -> dict[str, Any]:
    return await _call_mcp_tool(
        "apply_discount",
        {
            "product_id": product_id,
            "percent": percent,
        },
    )

async def create_order(
    items: list[dict[str, Any]],
    graph_thread_id: str | None = None,
) -> dict[str, Any]:
    return await _call_mcp_tool(
        "create_order",
        {
            "items": items,
            "graph_thread_id": graph_thread_id,
        },
    )

async def get_order_status(
    order_id: str,
) -> dict[str, Any]:
    return await _call_mcp_tool(
        "get_order_status",
        {
            "order_id": order_id,
        },
    )

search_catalog_tool = StructuredTool.from_function(
    coroutine=search_catalog,
    name="search_catalog",
    description=(
        "Search the ShopAgent product catalog using semantic similarity. "
        "Use this when the user is looking for products. "
        "Always apply explicit constraints from the user's request. "
        "If the user asks for a specific product type such as running shoes, "
        "use the appropriate category and subtype filters. "
        "For example, 'running shoes' should use category='running' "
        "and subtype='shoes'. "
        "Apply max_price and require_in_stock when specified."
    ),
)


find_products_by_name_tool = StructuredTool.from_function(
    coroutine=find_products_by_name,
    name="find_products_by_name",
    description=(
        "Find products by their exact names in the ShopAgent catalog. "
        "Includes products that are currently out of stock. "
        "Use this when the user explicitly names products to compare."
    ),
)


get_product_tool = StructuredTool.from_function(
    coroutine=get_product,
    name="get_product",
    description=(
        "Get detailed information about a specific "
        "product using its product ID."
    ),
)

check_inventory_tool = StructuredTool.from_function(
    coroutine=check_inventory,
    name="check_inventory",
    description=(
        "Check the current stock quantity and "
        "availability of a product."
    ),
)

apply_discount_tool = StructuredTool.from_function(
    coroutine=apply_discount,
    name="apply_discount",
    description=(
        "Apply a discount to a product. "
        "The seller enforces the maximum allowed discount. "
        "Use this only when a discount is appropriate."
    ),
)

create_order_tool = StructuredTool.from_function(
    coroutine=create_order,
    name="create_order",
    description=(
        "Create a ShopAgent order after validating "
        "products and inventory. "
        "Each item must contain product_id and quantity."
    ),
)

get_order_status_tool = StructuredTool.from_function(
    coroutine=get_order_status,
    name="get_order_status",
    description=(
        "Get the current status of a ShopAgent order. "
        "Use this to check whether an order has been paid."
    ),
)

MCP_TOOLS = [
    search_catalog_tool,
    find_products_by_name_tool,
    get_product_tool,
    check_inventory_tool,
    apply_discount_tool,
    create_order_tool,
    get_order_status_tool,
]
