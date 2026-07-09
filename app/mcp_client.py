"""MCP client bridge.

Connects to the hotel MCP server over stdio, discovers its tools, and
converts them into OpenAI function-calling schemas so the LLM can
request them. One persistent session is kept for the app's lifetime.
"""

from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class HotelMCPClient:
    def __init__(self, command: str, args: list[str] | None = None):
        self.command = command
        self.args = args or ["-m", "mcp_server.server"]
        self.stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None
        self.openai_tools: list[dict] = []

    async def connect(self) -> list[str]:
        self.stack = AsyncExitStack()
        params = StdioServerParameters(command=self.command, args=self.args)
        read, write = await self.stack.enter_async_context(stdio_client(params))
        self.session = await self.stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

        listed = await self.session.list_tools()
        # MCP tool schema -> OpenAI tool schema, so the model can call them
        self.openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in listed.tools
        ]
        return [tool.name for tool in listed.tools]

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self.session.call_tool(name, arguments)
        return result.content[0].text if result.content else "{}"

    async def close(self) -> None:
        if self.stack:
            await self.stack.aclose()
