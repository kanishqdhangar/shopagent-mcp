import asyncio

from langchain_core.messages import HumanMessage

from buyer_agent.graph import buyer_graph


async def main():
    user_request = (
        "Tell me about UrbanRun Lightweight Shoes. "
        "Give me its price, specifications, and description, "
        "and check whether it is currently in stock."
    )

    result = await buyer_graph.ainvoke(
        {
            "messages": [
                HumanMessage(content=user_request)
            ]
        }
    )

    final_message = result["messages"][-1]

    print("\nBuyer Agent Response:")
    print(final_message.content)


if __name__ == "__main__":
    asyncio.run(main())