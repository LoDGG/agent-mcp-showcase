"""Run the deterministic example with an actual SDK client/server boundary."""

import asyncio

from agent_showcase.agent import run_agent
from agent_showcase.mcp.client import EmailMCPClient
from agent_showcase.mcp.fake_email_server import create_server
from agent_showcase.mcp.store import FakeEmailStore
from agent_showcase.providers.fake import DEMO_REQUEST, FakeLLMProvider


async def main() -> None:
    store = FakeEmailStore()
    provider = FakeLLMProvider()
    print(f"User: {DEMO_REQUEST}")
    async with EmailMCPClient(create_server(store)) as client:
        answer = await run_agent(DEMO_REQUEST, provider, client)
    for messages, _ in provider.seen:
        if messages[-1].tool_result:
            result = messages[-1].tool_result
            print(f"MCP: {result.call.name} {result.call.arguments} -> {result.content}")
    print(f"Agent: {answer}")
    print(f"Final labels: {store.get_email('msg-invoice')['labels']}")


if __name__ == "__main__":
    asyncio.run(main())
