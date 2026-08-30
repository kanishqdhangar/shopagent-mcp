from typing import Any

from state import AgentState
from tools.mcp_tools import search_catalog


async def rag_search(state: AgentState) -> dict[str, Any]:
    parsed_filters = state.get("parsed_filters") or {}

    query = parsed_filters.get("search_query") or state["goal"]

    max_price = parsed_filters.get("budget")
    category = parsed_filters.get("category")
    subtype = parsed_filters.get("subtype")

    # Normalize catalog terminology.
    if subtype == "shoe":
        subtype = "shoes"

    result = await search_catalog(
        query=query,
        limit=5,
        max_price=max_price,
        require_in_stock=True,
        category=category,
        subtype=subtype,
    )

    candidates = [
        item["product"]
        for item in result.get("results", [])
        if item.get("product")
    ]

    return {
        "candidates": candidates,
    }