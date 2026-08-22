from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from buyer_agent.nodes.buyer_node import (
    BuyerState,
    buyer_node,
)
from buyer_agent.tools.mcp_tools import MCP_TOOLS


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
        "buyer_agent",
    )

    return builder.compile()


buyer_graph = build_buyer_graph()