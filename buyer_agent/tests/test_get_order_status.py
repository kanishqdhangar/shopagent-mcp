import asyncio

from tools.mcp_tools import get_order_status


ORDER_ID = "e719119f-c106-47c7-8eb0-1a7a5601718b"


async def main():
    result = await get_order_status(
        order_id=ORDER_ID,
    )

    print("\n=== GET ORDER STATUS TEST ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())