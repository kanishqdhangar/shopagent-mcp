from typing import Annotated, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from buyer_agent.config import settings
from buyer_agent.tools.mcp_tools import MCP_TOOLS


class BuyerState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.gemini_api_key,
)

llm_with_tools = llm.bind_tools(MCP_TOOLS)


async def buyer_node(state: BuyerState):
    response = await llm_with_tools.ainvoke(
        state["messages"]
    )

    return {
        "messages": [response]
    }