from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_SERVER_URL = "http://seller:8000/mcp/"


@asynccontextmanager
async def get_mcp_session():
    async with streamable_http_client(MCP_SERVER_URL) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:
            await session.initialize()

            yield session