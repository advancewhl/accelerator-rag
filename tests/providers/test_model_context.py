"""Standalone model imports and optional caller deadline compatibility."""

from contextvars import ContextVar
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import httpx

from accelerator_rag.providers.context import CURRENT, effective_timeout
from accelerator_rag.providers.model import OpenAICompatibleModelProvider
from accelerator_rag.domain.model import ChatMessage


def test_model_import_does_not_load_agent_runtime():
    source = str(Path(__file__).resolve().parents[2] / "src")
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "import accelerator_rag.providers.model; "
            "assert 'accelerator_rag.agent.budget' not in sys.modules",
            source,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_optional_deadline_and_legacy_caller_remain_compatible(monkeypatch):
    legacy = ContextVar("legacy_test_context", default=None)
    monkeypatch.setitem(
        sys.modules, "accelerator_rag.agent.budget", SimpleNamespace(CURRENT=legacy)
    )
    assert effective_timeout(120) == 120
    old_token = legacy.set(SimpleNamespace(remaining_seconds=lambda: 9))
    try:
        assert effective_timeout(120) == 9
        token = CURRENT.set(SimpleNamespace(remaining_seconds=lambda: 4))
        try:
            assert effective_timeout(120) == 4
            assert effective_timeout(2) == 2
        finally:
            CURRENT.reset(token)
        assert effective_timeout(120) == 9
    finally:
        legacy.reset(old_token)


def test_model_deadline_and_usage_work_without_agent():
    tokens = {}
    context = SimpleNamespace(
        remaining_seconds=lambda: 3, usage=SimpleNamespace(tokens=tokens)
    )

    def respond(request):
        assert request.extensions["timeout"]["read"] == 3
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"total_tokens": 7},
            },
        )

    token = CURRENT.set(context)
    try:
        with OpenAICompatibleModelProvider(
            "http://localhost:8000/v1", transport=httpx.MockTransport(respond)
        ) as provider:
            assert (
                provider.complete((ChatMessage(role="user", content="q"),), ()).content
                == "ok"
            )
        assert tokens == {"total_tokens": 7}
    finally:
        CURRENT.reset(token)
