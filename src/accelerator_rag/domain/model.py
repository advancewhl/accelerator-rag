"""Small typed OpenAI-compatible conversation contract."""

from __future__ import annotations

import json
from typing import Annotated, Literal, Protocol

from pydantic import Field, StrictStr, model_validator

from accelerator_rag.domain.common import DomainModel, Nonempty


class ToolCall(DomainModel):
    id: Nonempty
    name: Nonempty
    arguments: StrictStr

    def to_wire(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


class ChatMessage(DomainModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: StrictStr | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: Nonempty | None = None

    @model_validator(mode="after")
    def role_fields(self):
        if self.tool_calls and self.role != "assistant":
            raise ValueError("Only assistant messages can contain tool calls")
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("Tool replies must identify their call")
        if self.role != "assistant" and self.content is None:
            raise ValueError("Message content is required")
        return self

    def to_wire(self) -> dict:
        data = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [c.to_wire() for c in self.tool_calls]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


# Bound batch size independently from the graph tool-round limit.
AnnotatedCalls = Annotated[tuple[ToolCall, ...], Field(max_length=16)]


class AssistantResponse(DomainModel):
    content: StrictStr | None = None
    tool_calls: AnnotatedCalls = Field(default=())

    @model_validator(mode="after")
    def valid_response(self):
        if not self.tool_calls and not (self.content and self.content.strip()):
            raise ValueError("Empty assistant response")
        ids = [c.id for c in self.tool_calls]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate tool call IDs")
        return self

    def message(self) -> ChatMessage:
        return ChatMessage(
            role="assistant", content=self.content, tool_calls=self.tool_calls
        )


class ModelProviderError(RuntimeError):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code, self.reason = code, reason


class ModelProvider(Protocol):
    def complete(
        self,
        messages: tuple[ChatMessage, ...],
        tools: tuple[dict, ...],
        tool_choice: str = "auto",
    ) -> AssistantResponse: ...


def parse_arguments(raw: str) -> dict:
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite JSON value")

    if len(raw.encode("utf-8")) > 16384:
        raise ValueError("Tool arguments exceed size limit")
    value = json.loads(
        raw, object_pairs_hook=no_duplicates, parse_constant=reject_constant
    )
    if not isinstance(value, dict):
        raise ValueError("Tool arguments must be a JSON object")
    return value
