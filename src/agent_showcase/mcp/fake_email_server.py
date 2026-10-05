"""MCP tool adapter simplified from the existing fake email server."""

from typing import TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from agent_showcase.mcp.store import FakeEmailStore


class EmailMetadata(TypedDict):
    id: str
    sender: str
    subject: str
    labels: list[str]


class Email(EmailMetadata):
    body: str


class SearchResult(TypedDict):
    messages: list[EmailMetadata]


class LabelResult(TypedDict):
    message_id: str
    label: str
    added: bool
    labels: list[str]


class ArchiveResult(TypedDict):
    message_id: str
    archived: bool
    labels: list[str]


def create_server(store: FakeEmailStore | None = None) -> MCPServer:
    """Bind exactly four tools to an isolated, resettable synthetic store."""
    store = store if store is not None else FakeEmailStore()
    server = MCPServer("synthetic-email")

    def execute(operation):
        try:
            return operation()
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool()
    async def search_email(query: str = "") -> SearchResult:
        """Case-insensitive substring search; empty query returns all metadata."""
        return execute(lambda: {"messages": store.search_email(query)})

    @server.tool()
    async def get_email(message_id: str) -> Email:
        """Read a synthetic email body and labels by ID."""
        return execute(lambda: store.get_email(message_id))

    @server.tool()
    async def apply_label(message_id: str, label: str) -> LabelResult:
        """Add a non-empty label to one synthetic email, idempotently."""
        return execute(lambda: store.apply_label(message_id, label))

    @server.tool()
    async def archive_email(message_id: str) -> ArchiveResult:
        """Remove INBOX from one synthetic email, idempotently."""
        return execute(lambda: store.archive_email(message_id))

    return server


if __name__ == "__main__":
    create_server().run()
