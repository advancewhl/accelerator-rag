import json

import httpx
import pytest

from accelerator_rag.domain.model import ChatMessage, ModelProviderError
from accelerator_rag.providers.model import OpenAICompatibleModelProvider

MESSAGES = (ChatMessage(role="user", content="analyze"),)


def wire(calls=(), content=None):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": list(calls),
                }
            }
        ]
    }


def tool(id="call-1", arguments='{"date":"2026-10-08"}'):
    return {
        "id": id,
        "type": "function",
        "function": {"name": "waveform_list_runs", "arguments": arguments},
    }


@pytest.mark.parametrize("count", [0, 1, 2])
def test_response_and_request(count):
    calls = [tool(str(i)) for i in range(count)]

    def handler(r):
        assert r.url.path == "/v1/chat/completions"
        value = json.loads(r.content)
        assert value["messages"] == [{"role": "user", "content": "analyze"}]
        assert value["tool_choice"] == "auto"
        return httpx.Response(200, json=wire(calls, None if count else "answer"))

    with OpenAICompatibleModelProvider(
        "http://model/v1", transport=httpx.MockTransport(handler)
    ) as provider:
        result = provider.complete(MESSAGES, ({"type": "function"},))
    assert len(result.tool_calls) == count
    if count:
        assert json.loads(result.tool_calls[0].arguments)["date"] == "2026-10-08"
    else:
        assert result.content == "answer"


@pytest.mark.parametrize("arguments", ["{", "[]", '{"x":NaN}', '{"x":1,"x":2}', "1"])
def test_malformed_tool_arguments(arguments):
    with OpenAICompatibleModelProvider(
        "http://model/v1",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=wire([tool(arguments=arguments)]))
        ),
    ) as provider:
        result = provider.complete(MESSAGES, ())
    assert result.tool_calls[0].arguments == arguments


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        wire(),
        {"choices": [{"message": {"role": "tool", "content": "bad"}}]},
        wire([tool(), tool()]),
        wire(content=123),
    ],
)
def test_unexpected_response(payload):
    with OpenAICompatibleModelProvider(
        "http://model/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    ) as provider:
        with pytest.raises(ModelProviderError):
            provider.complete(MESSAGES, ())


@pytest.mark.parametrize("failure", ["timeout", "connection", "500", "json"])
def test_transport_errors(failure):
    def handler(r):
        if failure == "timeout":
            raise httpx.ReadTimeout("secret", request=r)
        if failure == "connection":
            raise httpx.ConnectError("secret", request=r)
        return httpx.Response(500 if failure == "500" else 200, content=b"private")

    with OpenAICompatibleModelProvider(
        "http://model/v1", transport=httpx.MockTransport(handler)
    ) as provider:
        with pytest.raises(ModelProviderError) as exc:
            provider.complete(MESSAGES, ())
    assert "secret" not in str(exc.value) and "private" not in str(exc.value)


def test_assistant_tool_and_tool_reply_serialization():
    from accelerator_rag.domain.model import ToolCall

    call = ToolCall(id="1", name="waveform_list_runs", arguments="{}")
    messages = (
        ChatMessage(role="assistant", tool_calls=(call,)),
        ChatMessage(role="tool", tool_call_id="1", content='{"result":{}}'),
    )

    def handler(r):
        wire_messages = json.loads(r.content)["messages"]
        assert wire_messages[0]["tool_calls"][0] == call.to_wire()
        assert wire_messages[1]["tool_call_id"] == "1"
        return httpx.Response(200, json=wire(content="done"))

    with OpenAICompatibleModelProvider(
        "http://model/v1", transport=httpx.MockTransport(handler)
    ) as provider:
        assert provider.complete(messages, ()).content == "done"


@pytest.mark.parametrize(
    "calls",
    [
        None,
        {},
        "bad",
        0,
        False,
        [{"type": "function", "function": {"name": "tool", "arguments": "{}"}}],
        [{"id": "1", "type": "function"}],
        [tool(arguments={})],
        [tool(arguments=None)],
        [{**tool(), "type": "other"}],
        [tool(id="")],
        [{**tool(), "function": {"name": "", "arguments": "{}"}}],
    ],
)
def test_invalid_tool_envelope(calls):
    payload = wire(content="fallback content must not hide invalid envelope")
    payload["choices"][0]["message"]["tool_calls"] = calls
    with OpenAICompatibleModelProvider(
        "http://model/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    ) as provider:
        with pytest.raises(ModelProviderError) as exc:
            provider.complete(MESSAGES, ())
    assert exc.value.code == "INVALID_RESPONSE"


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "INVALID_REQUEST"),
        (404, "INVALID_REQUEST"),
        (422, "INVALID_REQUEST"),
        (401, "AUTH"),
        (403, "AUTH"),
        (429, "RATE_LIMIT"),
        (500, "UNAVAILABLE"),
        (502, "UNAVAILABLE"),
        (503, "UNAVAILABLE"),
        (504, "UNAVAILABLE"),
        (418, "UNAVAILABLE"),
    ],
)
def test_http_error_mapping_and_safe_logging(status, code, caplog):
    with OpenAICompatibleModelProvider(
        "http://model/v1",
        api_key="test-secret",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(status, content=b"private-response-body")
        ),
    ) as provider:
        with pytest.raises(ModelProviderError) as exc:
            provider.complete(MESSAGES, ())
    assert exc.value.code == code
    assert f"status={status}" in caplog.text and "host=model" in caplog.text
    for secret in ("private-response-body", "test-secret", "Authorization"):
        assert secret not in caplog.text and secret not in str(exc.value)


def test_transport_timeout_code():
    def handler(request):
        raise httpx.ReadTimeout("private timeout details", request=request)

    with OpenAICompatibleModelProvider(
        "http://model/v1", transport=httpx.MockTransport(handler)
    ) as provider:
        with pytest.raises(ModelProviderError) as exc:
            provider.complete(MESSAGES, ())
    assert exc.value.code == "TIMEOUT"
