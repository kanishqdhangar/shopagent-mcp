import asyncio

from mcp_client import get_mcp_session


async def main():
    async with get_mcp_session() as session:
        result = await session.list_tools()

        print("\n=== SELLER MCP TOOLS ===")

        for tool in result.tools:
            print(f"\nNAME: {tool.name}")
            print(f"DESCRIPTION: {tool.description}")
            print(f"SCHEMA: {tool.input_schema}")


if __name__ == "__main__":
    asyncio.run(main())