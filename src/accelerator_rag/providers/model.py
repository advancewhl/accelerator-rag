"""OpenAI-compatible HTTP chat adapter, independent of inference server internals."""

from __future__ import annotations

import logging
import time

import httpx
from .context import current_context, effective_timeout

from pydantic import ValidationError

from accelerator_rag.domain.model import (
    AssistantResponse,
    ChatMessage,
    ModelProviderError,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleModelProvider:
    def __init__(
        self,
        base_url: str,
        model_name: str = "qwen3-vl",
        *,
        connect_timeout: float = 2,
        read_timeout: float = 120,
        transport: httpx.BaseTransport | None = None,
        api_key: str | None = None,
    ):
        from math import isfinite

        for value in (connect_timeout, read_timeout):
            if isinstance(value, bool) or not isfinite(value) or value <= 0:
                raise ValueError("Model timeouts must be positive and finite")
        url = httpx.URL(base_url)
        if (
            url.scheme not in ("http", "https")
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
            or not model_name.strip()
        ):
            raise ValueError("Invalid model URL or model name")
        self.read_timeout = read_timeout
        self.model_name = model_name
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            transport=transport,
            timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            trust_env=False,
            follow_redirects=False,
        )

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def complete(
        self,
        messages: tuple[ChatMessage, ...],
        tools: tuple[dict, ...],
        tool_choice: str = "auto",
    ) -> AssistantResponse:
        started = time.monotonic()
        payload = {
            "model": self.model_name,
            "messages": [m.to_wire() for m in messages],
        }
        if tools:
            payload.update(tools=list(tools), tool_choice=tool_choice)
        logger.info(
            "model request model=%s messages=%d tools=%d",
            self.model_name,
            len(messages),
            len(tools),
        )
        try:
            response = self._http.post(
                "chat/completions",
                json=payload,
                timeout=effective_timeout(self.read_timeout),
            )
        except httpx.TimeoutException as exc:
            raise ModelProviderError("TIMEOUT", "Model HTTP timeout") from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError("UNAVAILABLE", "Model HTTP unavailable") from exc
        if response.status_code != 200:
            status = response.status_code
            code = {
                400: "INVALID_REQUEST",
                404: "INVALID_REQUEST",
                422: "INVALID_REQUEST",
                401: "AUTH",
                403: "AUTH",
                429: "RATE_LIMIT",
            }.get(status, "UNAVAILABLE")
            logger.warning(
                "model HTTP error status=%d host=%s", status, self._http.base_url.host
            )
            raise ModelProviderError(code, "Model server rejected request")
        try:
            data = response.json()
            context = current_context()
            tokens = getattr(getattr(context, "usage", None), "tokens", None)
            if isinstance(tokens, dict) and isinstance(data.get("usage"), dict):
                for key, value in data["usage"].items():
                    if (
                        isinstance(value, int)
                        and not isinstance(value, bool)
                        and value >= 0
                    ):
                        tokens[key] = tokens.get(key, 0) + value
            choices = data["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError("Missing choices")
            message = choices[0]["message"]
            if message["role"] != "assistant":
                raise ValueError("Expected assistant role")
            raw_calls = message.get("tool_calls", [])
            if not isinstance(raw_calls, list):
                raise ValueError("tool_calls must be a list")
            calls = []
            for call in raw_calls:
                if call["type"] != "function":
                    raise ValueError("Unsupported tool call type")
                function = call["function"]
                typed = ToolCall(
                    id=call["id"],
                    name=function["name"],
                    arguments=function["arguments"],
                )
                calls.append(typed)
            result = AssistantResponse(
                content=message.get("content"), tool_calls=tuple(calls)
            )
        except (
            ValueError,
            KeyError,
            TypeError,
            IndexError,
            ValidationError,
            RecursionError,
        ) as exc:
            raise ModelProviderError(
                "INVALID_RESPONSE", "Invalid model response"
            ) from exc
        logger.info(
            "model response tool_calls=%d duration_seconds=%.3f",
            len(result.tool_calls),
            time.monotonic() - started,
        )
        return result
