from typing import Any, Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from nodes.buyer_node import buyer_node
from tools.mcp_tools import MCP_TOOLS
from nodes.tool_result_node import extract_products

class BuyerState(TypedDict):
    messages: Annotated[list, add_messages]
    products: list[dict[str, Any]]


def should_continue(state: BuyerState):
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"

    return END


def build_buyer_graph():
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

    return builder.compile()


buyer_graph = build_buyer_graph()