"""Call the ShopAgent seller catalog MCP tool without importing app code."""

import argparse
import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def call_catalog(query: str, server_url: str) -> None:
    async with streamable_http_client(server_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_catalog", {"query": query, "limit": 5}
            )
            if hasattr(result, "model_dump"):
                print(json.dumps(result.model_dump(mode="json"), indent=2))
            else:
                print(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search the ShopAgent seller catalog via MCP"
    )
    parser.add_argument("query", help="Natural-language product search")
    args = parser.parse_args()
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/")
    asyncio.run(call_catalog(args.query, server_url))


if __name__ == "__main__":
    main()
