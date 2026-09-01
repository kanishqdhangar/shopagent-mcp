import asyncio

from tools.mcp_tools import create_order


PRODUCT_ID = "eb5e2833-d31c-44d1-95b2-6ea108610b89"


async def main():
    result = await create_order(
        items=[
            {
                "product_id": PRODUCT_ID,
                "quantity": 1,
            }
        ]
    )

    print("\n=== CREATE ORDER TOOL TEST ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())