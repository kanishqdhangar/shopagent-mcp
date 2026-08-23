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


SYSTEM_PROMPT = """
You are the ShopAgent Buyer Agent.

You help users search and compare products from the ShopAgent catalog.

IMPORTANT:

- Use search_catalog when the user is looking for new products.
- Respect explicit constraints such as price, stock, category, subtype,
  size, color, and other product requirements.
- For follow-up requests, use ONLY the products currently provided in
  CURRENT PRODUCT CONTEXT when the request refers to previous results.
- Never introduce products that are not present in CURRENT PRODUCT CONTEXT
  for a follow-up request.
- If the user says "cheaper", return only products from CURRENT PRODUCT
  CONTEXT that satisfy the cheaper request.
- If the user says "more expensive", return only products from CURRENT
  PRODUCT CONTEXT that satisfy the request.
- If the user says "show black ones", "UK 8", etc., filter CURRENT PRODUCT
  CONTEXT when possible.
- Do not call search_catalog for a follow-up filtering request when
  CURRENT PRODUCT CONTEXT already contains the relevant products.
- Do not forget previous search constraints during follow-up requests.
- Never recommend products that violate an explicit user constraint.
- Only claim a product is in stock when its stock_qty is greater than zero.
- Give concise, useful shopping recommendations.
"""

async def buyer_node(state: BuyerState):
    products = state.get("products", [])
    active_filters = state.get("active_filters", {})

    context = SystemMessage(
        content=(
            SYSTEM_PROMPT
            + "\n\nCURRENT PRODUCT CONTEXT:\n"
            + str(products)
            + "\n\nACTIVE FILTERS:\n"
            + str(active_filters)
        )
    )

    response = await llm_with_tools.ainvoke(
        [context, *state["messages"]]
    )

    return {
        "messages": [response],
        "products": products,
        "active_filters": active_filters,
    }