import json
from typing import Any

from langchain_core.tools import StructuredTool

from mcp_client import get_mcp_session

from services.product_filter import filter_products

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


search_catalog_tool = StructuredTool.from_function(
    coroutine=search_catalog,
    name="search_catalog",
    description=(
        "Search the ShopAgent product catalog using "
        "semantic similarity. Use this when the user "
        "is looking for products. Apply max_price, "
        "require_in_stock, category, and subtype when "
        "the user specifies those constraints."
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


MCP_TOOLS = [
    search_catalog_tool,
    get_product_tool,
    check_inventory_tool,
]