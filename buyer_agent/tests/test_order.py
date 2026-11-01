import asyncio

from mcp_client import get_mcp_session


PRODUCT_ID = "eb5e2833-d31c-44d1-95b2-6ea108610b89"


async def main():
    async with get_mcp_session() as session:

        print("\n=== CREATE ORDER TEST ===")

        result = await session.call_tool(
            "create_order",
            {
                "items": [
                    {
                        "product_id": PRODUCT_ID,
                        "quantity": 1,
                    }
                ]
            },
        )

        print(result.content)


if __name__ == "__main__":
    asyncio.run(main())