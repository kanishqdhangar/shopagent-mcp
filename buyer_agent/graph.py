from typing import Any, Annotated, TypedDict

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from nodes.buyer_node import buyer_node
from tools.mcp_tools import MCP_TOOLS
from nodes.tool_result_node import extract_products


def replace_products(
    current: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return new


def replace_filters(
    current: dict[str, Any],
    new: dict[str, Any],
) -> dict[str, Any]:
    return new


class BuyerState(TypedDict, total=False):
    messages: Annotated[list, add_messages]

    products: Annotated[
        list[dict[str, Any]],
        replace_products,
    ]

    active_filters: Annotated[
        dict[str, Any],
        replace_filters,
    ]


def should_continue(state: BuyerState):
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return END


async def build_buyer_graph():
    checkpointer = AsyncRedisSaver(
        redis_url="redis://redis:6379"
    )

    await checkpointer.asetup()

    builder = StateGraph(BuyerState)

    builder.add_node(
        "buyer_agent",
        buyer_node,
    )

    builder.add_node(
        "tools",
        ToolNode(MCP_TOOLS),
    )

    builder.add_node(
        "extract_products",
        extract_products,
    )

    builder.add_edge(
        START,
        "buyer_agent",
    )

    builder.add_conditional_edges(
        "buyer_agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )

    builder.add_edge(
        "tools",
        "extract_products",
    )

    builder.add_edge(
        "extract_products",
        "buyer_agent",
    )

    return builder.compile(
        checkpointer=checkpointer,
    )