import asyncio

from langchain_core.messages import HumanMessage

from graph import buyer_graph


async def main():
    user_request = (
        "Find me lightweight running shoes "
        "for daily training under ₹3500. "
        "Only recommend products that are in stock."
    )

    result = await buyer_graph.ainvoke(
        {
            "messages": [
                HumanMessage(content=user_request)
            ],
            "products": [],
            "active_filters": {},
        }
    )

    final_message = result["messages"][-1]

    print("\nBuyer Agent Response:")
    print(final_message.content)
    print("\nProducts:")
    print(result["products"])


if __name__ == "__main__":
    asyncio.run(main())