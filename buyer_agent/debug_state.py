import asyncio

from langchain_core.messages import HumanMessage

from graph import buyer_graph


async def main():
    result = await buyer_graph.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Find lightweight running shoes "
                        "under ₹3500. "
                        "Only recommend products that are in stock."
                    )
                )
            ],
            "products": [],
            "active_filters": {},
        },
        config={
            "configurable": {
                "thread_id": "debug-filters",
            }
        },
    )

    for message in result["messages"]:
        print("\nTYPE:", type(message).__name__)
        print("MESSAGE:")
        print(message)
        print("\n---")


if __name__ == "__main__":
    asyncio.run(main())