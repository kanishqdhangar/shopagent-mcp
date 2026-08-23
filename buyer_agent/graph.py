from typing import Any, Annotated, TypedDict

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from nodes.buyer_node import buyer_node
from tools.mcp_tools import MCP_TOOLS
from nodes.tool_result_node import extract_products
from nodes.followup_filter_node import followup_filter_node



class BuyerState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    products: list[dict[str, Any]]
    active_filters: dict[str, Any]

def should_continue(state: BuyerState):
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return END


def should_use_previous_products(state: BuyerState):
    products = state.get("products", [])

    if not products:
        return "buyer_agent"

    last_user_message = ""

    for message in reversed(state["messages"]):
        if getattr(message, "type", None) == "human":
            last_user_message = message.content.lower()
            break

    followup_phrases = [
        "cheaper",
        "cheapest",
        "more expensive",
        "most expensive",
        "black ones",
        "white ones",
        "grey ones",
        "gray ones",
        "blue ones",
        "red ones",
        "green ones",
        "only show",
        "what about",
        "uk 6",
        "uk 7",
        "uk 8",
        "uk 9",
        "uk 10",
    ]

    if any(
        phrase in last_user_message
        for phrase in followup_phrases
    ):
        return "followup_filter"

    return "buyer_agent"


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

    builder.add_node(
        "followup_filter",
        followup_filter_node,
    )

    builder.add_conditional_edges(
        START,
        should_use_previous_products,
        {
            "followup_filter": "followup_filter",
            "buyer_agent": "buyer_agent",
        },
    )

    builder.add_edge(
        "followup_filter",
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