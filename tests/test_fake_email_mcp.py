"""SDK-level cases adapted from the original fake MCP tests."""

import pytest

from agent_showcase.core import ToolCall
from agent_showcase.mcp.client import EmailMCPClient
from agent_showcase.mcp.fake_email_server import create_server
from agent_showcase.mcp.store import FakeEmailStore


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with EmailMCPClient(create_server()) as connected:
        yield connected


@pytest.mark.anyio
async def test_discovery_and_search_get(client):
    assert {tool.name for tool in await client.discover()} == {
        "search_email", "get_email", "apply_label", "archive_email",
    }
    found = await client.call(ToolCall("search_email", {"query": "SEPTEMBER INVOICE"}))
    assert not found.is_error
    assert [message["id"] for message in found.content["messages"]] == ["msg-invoice"]
    assert "body" not in found.content["messages"][0]
    fetched = await client.call(ToolCall("get_email", {"message_id": "msg-invoice"}))
    assert fetched.content["subject"] == "September invoice"
    assert "Synthetic" in fetched.content["body"]
    all_messages = await client.call(ToolCall("search_email", {}))
    assert len(all_messages.content["messages"]) == 2
    empty = await client.call(ToolCall("search_email", {"query": "no match"}))
    assert empty.content["messages"] == []


@pytest.mark.anyio
async def test_apply_label_and_archive_are_idempotent(client):
    call = ToolCall("apply_label", {"message_id": "msg-invoice", "label": "TO_REVIEW"})
    assert (await client.call(call)).content["added"] is True
    assert (await client.call(call)).content["added"] is False
    archive = ToolCall("archive_email", {"message_id": "msg-invoice"})
    assert (await client.call(archive)).content["archived"] is True
    assert (await client.call(archive)).content["archived"] is False
    fetched = await client.call(ToolCall("get_email", {"message_id": "msg-invoice"}))
    assert fetched.content["labels"] == ["TO_REVIEW"]


@pytest.mark.anyio
@pytest.mark.parametrize("call", [
    ToolCall("get_email", {"message_id": "missing"}),
    ToolCall("archive_email", {"message_id": "missing"}),
    ToolCall("apply_label", {"message_id": "msg-invoice", "label": " "}),
    ToolCall("apply_label", {"message_id": "msg-invoice", "label": "BAD\nLABEL"}),
])
async def test_server_errors_are_structured(client, call):
    result = await client.call(call)
    assert result.is_error
    assert result.content["error"]


def test_store_isolation_reset_and_defensive_copies():
    first, second = FakeEmailStore(), FakeEmailStore()
    first.apply_label("msg-invoice", "TO_REVIEW")
    assert second.get_email("msg-invoice")["labels"] == ["INBOX"]
    fetched = first.get_email("msg-invoice")
    fetched["labels"].clear()
    assert first.get_email("msg-invoice")["labels"] == ["INBOX", "TO_REVIEW"]
    first.reset()
    assert first.get_email("msg-invoice")["labels"] == ["INBOX"]
