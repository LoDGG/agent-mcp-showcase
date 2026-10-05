"""Focused cases adapted from the original bounded agent tests."""

import pytest

from agent_showcase.agent import MAX_AGENT_ITERATIONS, MAX_TOOL_CALLS, AgentError, SafetyLimitError, run_agent
from agent_showcase.core import ModelResponse, ToolCall
from agent_showcase.mcp.client import EmailMCPClient
from agent_showcase.mcp.fake_email_server import create_server
from agent_showcase.mcp.store import FakeEmailStore
from agent_showcase.providers.fake import DEMO_REQUEST, FakeLLMProvider


@pytest.fixture
def anyio_backend():
    return "asyncio"


class CountingClient(EmailMCPClient):
    def __init__(self, server):
        super().__init__(server)
        self.calls = []

    async def call(self, call):
        self.calls.append(call)
        return await super().call(call)


def request(name="search_email", **arguments):
    return ModelResponse(tool_calls=[ToolCall(name, arguments)])


@pytest.mark.anyio
async def test_successful_search_get_label_and_final():
    store = FakeEmailStore()
    provider = FakeLLMProvider()
    async with CountingClient(create_server(store)) as client:
        answer = await run_agent(DEMO_REQUEST, provider, client)
    assert answer == "September invoice labeled TO_REVIEW."
    assert store.get_email("msg-invoice")["labels"] == ["INBOX", "TO_REVIEW"]
    assert [call.name for call in client.calls] == ["search_email", "get_email", "apply_label"]
    assert len(provider.seen) == 4
    assert provider.seen[1][0][-1].tool_result.content["messages"][0]["id"] == "msg-invoice"
    assert provider.seen[2][0][-1].tool_result.content["body"]
    assert provider.seen[3][0][-1].tool_result.content["added"] is True


@pytest.mark.anyio
async def test_four_iteration_bound():
    assert MAX_AGENT_ITERATIONS == 4
    provider = FakeLLMProvider([request() for _ in range(5)])
    async with CountingClient(create_server()) as client:
        with pytest.raises(SafetyLimitError, match="Maximum agent iterations"):
            await run_agent("Keep searching", provider, client)
    assert len(provider.seen) == 4
    assert len(client.calls) == 3  # No tool runs on the final iteration.


@pytest.mark.anyio
async def test_three_tool_call_bound_with_batched_calls():
    assert MAX_TOOL_CALLS == 3
    provider = FakeLLMProvider([ModelResponse(tool_calls=[ToolCall("search_email", {}) for _ in range(4)])])
    async with CountingClient(create_server()) as client:
        with pytest.raises(SafetyLimitError, match="Maximum tool calls"):
            await run_agent("Keep searching", provider, client)
    assert len(client.calls) == 3
    assert len(provider.seen) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("decision, error", [
    ({"tool_calls": []}, "Malformed provider"),
    (ModelResponse(text=42), "Malformed provider"),
    (ModelResponse(tool_calls=None), "Malformed provider"),
    (ModelResponse(tool_calls=[{}]), "Malformed tool"),
    (request("delete_email", message_id="msg-invoice"), "Unauthorized or unknown"),
    (request("get_email", wrong="id"), "Invalid arguments"),
    (request("get_email", message_id=42), "Invalid arguments"),
    (request("search_email", query="invoice", extra=True), "Invalid arguments"),
    (ModelResponse(tool_calls=[ToolCall("get_email", [])]), "must be an object"),
    (ModelResponse(tool_calls=[ToolCall("search_email", {}), ToolCall("execute_shell", {})]), "Unauthorized or unknown"),
])
async def test_invalid_decision_rejected_before_any_execution(decision, error):
    provider = FakeLLMProvider([decision])
    async with CountingClient(create_server()) as client:
        with pytest.raises(AgentError, match=error):
            await run_agent("Invalid decision", provider, client)
    assert client.calls == []


@pytest.mark.anyio
async def test_tool_error_returns_to_provider():
    provider = FakeLLMProvider([
        request("get_email", message_id="missing"), ModelResponse("Tool failed."),
    ])
    async with CountingClient(create_server()) as client:
        assert await run_agent("Get", provider, client) == "Tool failed."
    assert provider.seen[1][0][-1].tool_result.is_error
