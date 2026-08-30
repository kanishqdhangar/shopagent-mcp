from typing import Any

from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from state import AgentState
from nodes.parse_intent import parse_intent
from nodes.rag_search import rag_search
from nodes.compare_options import compare_options
from nodes.check_upsell import check_upsell

def route_on_confidence(state: AgentState):
    confidence = state.get("confidence", 0.0)

    if confidence < 0.5:
        return "retry"

    return "proceed"


async def build_buyer_graph():
    checkpointer = AsyncRedisSaver(
        redis_url="redis://redis:6379"
    )

    await checkpointer.asetup()

    builder = StateGraph(AgentState)

    builder.add_node(
        "parse_intent",
        parse_intent,
    )

    builder.add_node(
        "rag_search",
        rag_search,
    )

    builder.add_node(
        "compare_options",
        compare_options,
    )

    builder.add_node(
        "check_upsell",
        check_upsell,
    )

    builder.add_edge(
        START,
        "parse_intent",
    )

    builder.add_edge(
        "parse_intent",
        "rag_search",
    )

    builder.add_edge(
        "rag_search",
        "compare_options",
    )

    builder.add_edge(
        "check_upsell",
        END,
    )
    
    builder.add_conditional_edges(
        "compare_options",
        route_on_confidence,
        {
            "retry": "parse_intent",
            "proceed": "check_upsell",
        },
    )

    return builder.compile(
        checkpointer=checkpointer,
    )