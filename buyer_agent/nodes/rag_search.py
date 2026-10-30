
from typing import Any

from state import AgentState
from tools.mcp_tools import (
    search_catalog,
    find_products_by_name,
)


async def rag_search(state: AgentState) -> dict[str, Any]:
    parsed_filters = state.get("parsed_filters") or {}

    intent_type = parsed_filters.get("intent_type", "search")
    query = parsed_filters.get("search_query") or state["goal"]

    max_price = parsed_filters.get("budget")
    category = parsed_filters.get("category")
    subtype = parsed_filters.get("subtype")

    # Normalize catalog terminology.
    if subtype == "shoe":
        subtype = "shoes"

    # --------------------------------------------------
    # 1. Explicit product comparison
    # --------------------------------------------------
    if intent_type == "compare":
        product_names = parsed_filters.get("product_names") or []

        if product_names:
            result = await find_products_by_name(
                product_names=product_names,
            )

            candidates = [
                item
                for item in result.get("results", [])
                if item
            ]

            # Preserve the user's requested product order.
            name_lookup = {
                item.get("name", "").strip().lower(): item
                for item in candidates
            }

            ordered_candidates = []

            for name in product_names:
                product = name_lookup.get(name.strip().lower())

                if product:
                    ordered_candidates.append(product)

            candidates = ordered_candidates

        else:
            # No explicit names: fall back to semantic retrieval.
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

    # --------------------------------------------------
    # 2. Restock / reorder
    # --------------------------------------------------
    elif intent_type == "restock":
        result = await search_catalog(
            query=query,
            limit=5,
            max_price=max_price,
            require_in_stock=False,
            category=category,
            subtype=subtype,
        )

        candidates = [
            item["product"]
            for item in result.get("results", [])
            if item.get("product")
        ]

    # --------------------------------------------------
    # 3. Normal product search
    # --------------------------------------------------
    else:
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
