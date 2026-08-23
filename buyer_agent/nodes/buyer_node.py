from typing import Annotated, TypedDict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph.message import add_messages

from config import settings
from tools.mcp_tools import MCP_TOOLS


class BuyerState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    products: list[dict[str, Any]]
    active_filters: dict[str, Any]


llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.gemini_api_key,
)

llm_with_tools = llm.bind_tools(MCP_TOOLS)


async def buyer_node(state: BuyerState):
    active_filters = state.get("active_filters", {})

    system_prompt = """
You are ShopAgent, an AI shopping assistant.

You help users find products using the available catalog tools.

IMPORTANT FOLLOW-UP RULE:

When active shopping filters exist, preserve them across follow-up
requests unless the user explicitly changes or removes a filter.

For example, if the previous request established:
- category: running shoes
- max price: ₹3500
- require in-stock: true

and the user says:
"Show me the cheaper ones"

you must continue searching only within:
- running shoes
- under ₹3500
- in-stock products

The phrase "cheaper ones" means prioritize/filter the existing
product context by price. It does NOT mean searching the entire catalog.

Never remove an existing shopping constraint unless the user explicitly
asks you to change or remove it.

Use the available tools whenever product information is required.
"""

    if active_filters:
        system_prompt += f"""

CURRENT ACTIVE SHOPPING FILTERS:
{active_filters}

These filters came from the user's previous shopping request.
Preserve them for the current request unless the user explicitly
changes them.
"""

    messages = [
        SystemMessage(content=system_prompt),
        *state["messages"],
    ]

    response = await llm_with_tools.ainvoke(messages)

    return {
        "messages": [response]
    }