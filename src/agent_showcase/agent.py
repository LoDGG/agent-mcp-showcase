"""Application-owned tool authorization and bounded agent loop."""

import logging

from jsonschema import ValidationError, validate

from agent_showcase.core import ModelResponse, ToolCall, Message, ToolSpec, ToolResult
from agent_showcase.mcp.client import EmailMCPClient
from agent_showcase.providers.base import LLMProvider

MAX_AGENT_ITERATIONS = 4
MAX_TOOL_CALLS = 3
AUTHORIZED_TOOLS = frozenset({"search_email", "get_email", "apply_label", "archive_email"})
logger = logging.getLogger(__name__)


class AgentError(Exception):
    pass


class SafetyLimitError(AgentError):
    pass


def validate_response(response: object, tools: dict[str, ToolSpec]) -> ModelResponse:
    """Validate the whole decision before allowing any side effects."""
    if (not isinstance(response, ModelResponse) or not isinstance(response.text, str)
            or not isinstance(response.tool_calls, list)):
        raise AgentError("Malformed provider response")
    for call in response.tool_calls:
        if not isinstance(call, ToolCall) or not isinstance(call.name, str):
            raise AgentError("Malformed tool call")
        if call.name not in AUTHORIZED_TOOLS or call.name not in tools:
            raise AgentError(f"Unauthorized or unknown tool: {call.name}")
        if not isinstance(call.arguments, dict):
            raise AgentError("Tool arguments must be an object")
        try:
            validate(call.arguments, tools[call.name].input_schema)
        except ValidationError as exc:
            raise AgentError(f"Invalid arguments for {call.name}: {exc.message}") from exc
    return response


async def run_agent(prompt: str, provider: LLMProvider, mcp: EmailMCPClient) -> str:
    discovered = await mcp.discover()
    tools: dict[str, ToolSpec] = {tool.name: tool for tool in discovered if tool.name in AUTHORIZED_TOOLS}
    messages = [Message("user", prompt)]
    count = 0
    for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
        logger.info("iteration=%s/%s tool_calls=%s/%s", iteration, MAX_AGENT_ITERATIONS, count, MAX_TOOL_CALLS)
        response = validate_response(
            await provider.complete(list(messages), list(tools.values())), tools
        )
        if not response.tool_calls:
            logger.info("model completion iteration=%s", iteration)
            return response.text
        if iteration == MAX_AGENT_ITERATIONS:
            logger.warning("safety-limit termination iterations=%s/%s", iteration, MAX_AGENT_ITERATIONS)
            raise SafetyLimitError("Maximum agent iterations reached")
        messages.append(Message("assistant", response.text, response.tool_calls))
        for call in response.tool_calls:
            logger.info("requested_tool=%s tool_calls=%s/%s", call.name, count, MAX_TOOL_CALLS)
            if count >= MAX_TOOL_CALLS:
                raise SafetyLimitError("Maximum tool calls reached")
            count += 1
            try:
                result: ToolResult = await mcp.call(call)
            except Exception:
                logger.exception("MCP failure tool=%s", call.name)
                raise
            logger.info("MCP %s tool=%s", "failure" if result.is_error else "success", call.name)
            messages.append(Message("tool", tool_result=result))
    logger.warning("safety-limit termination iterations=%s/%s", MAX_AGENT_ITERATIONS, MAX_AGENT_ITERATIONS)
    raise SafetyLimitError("Maximum agent iterations reached")
