"""Deterministic decision maker; no network or model credentials."""

from collections.abc import Iterable

from agent_showcase.core import Message, ModelResponse, ToolCall, ToolSpec

DEMO_REQUEST = "Find the September invoice and label it TO_REVIEW."


class FakeLLMProvider:
    """Scripted test double, or a result-driven policy for the single demo request."""

    def __init__(self, responses: Iterable[ModelResponse] | None = None) -> None:
        self.responses = iter(responses) if responses is not None else None
        self.seen: list[tuple[list[Message], list[ToolSpec]]] = []

    async def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        self.seen.append((messages, tools))
        if self.responses is not None:
            return next(self.responses)
        if messages[0].text != DEMO_REQUEST:
            return ModelResponse(f"This fake provider supports only: {DEMO_REQUEST}")
        results = [message.tool_result for message in messages if message.tool_result]
        if not results:
            return ModelResponse(tool_calls=[ToolCall("search_email", {"query": "September invoice"})])
        result = results[-1]
        if result.is_error:
            return ModelResponse("The email tool failed; workflow stopped.")
        if result.call.name == "search_email":
            matches = result.content["messages"]
            if len(matches) != 1:
                return ModelResponse("Expected one invoice; workflow stopped.")
            call = ToolCall("get_email", {"message_id": matches[0]["id"]})
        elif result.call.name == "get_email":
            call = ToolCall("apply_label", {"message_id": result.content["id"], "label": "TO_REVIEW"})
        elif result.call.name == "apply_label" and "TO_REVIEW" in result.content["labels"]:
            return ModelResponse("September invoice labeled TO_REVIEW.")
        else:
            return ModelResponse("Unexpected tool result; workflow stopped.")
        return ModelResponse(tool_calls=[call])
