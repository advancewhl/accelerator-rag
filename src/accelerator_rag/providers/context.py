"""Optional caller deadlines without requiring an Agent runtime installation."""

from contextvars import ContextVar
import sys
from typing import Protocol


class RequestContext(Protocol):
    def remaining_seconds(self) -> float: ...


CURRENT: ContextVar[RequestContext | None] = ContextVar(
    "model_request_context", default=None
)


def current_context():
    context = CURRENT.get()
    if context is not None:
        return context
    # Existing Agent callers own a separate ContextVar. Adapt only an already
    # loaded runtime; a standalone RAG import must never import or start Agent.
    legacy = sys.modules.get("accelerator_rag.agent.budget")
    return legacy.CURRENT.get() if legacy is not None else None


def effective_timeout(configured):
    context = current_context()
    return min(configured, context.remaining_seconds()) if context else configured
