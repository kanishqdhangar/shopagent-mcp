import asyncio

from mcp_client import get_mcp_session


PRODUCT_ID = "eb5e2833-d31c-44d1-95b2-6ea108610b89"


async def main():
    async with get_mcp_session() as session:

        print("\n=== DISCOUNT TEST ===")

        for percent in [10, 15, 20]:
            result = await session.call_tool(
                "apply_discount",
                {
                    "product_id": PRODUCT_ID,
                    "percent": percent,
                },
            )

            print(f"\nDISCOUNT: {percent}%")
            print(result.content)


if __name__ == "__main__":
    asyncio.run(main())