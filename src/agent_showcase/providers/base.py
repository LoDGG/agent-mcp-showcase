"""Provider interface extracted from the provider-neutral core contract."""

from typing import Protocol

from agent_showcase.core import Message, ModelResponse, ToolSpec


class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse: ...
