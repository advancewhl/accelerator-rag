"""Bounded GPU retrieval; generation and evidence are request local."""

from threading import Lock
from time import perf_counter
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from accelerator_rag.retrieval.scope import RetrievalScope, default_scope
from .answer import generate, resolve
from .context import EvidenceContextBuilder

logger = logging.getLogger(__name__)
UNKNOWN_RELEASE = "unknown"


class RagService:
    def __init__(
        self,
        retriever,
        provider,
        *,
        requirement_retriever=None,
        count_tokens=None,
        trace_dir=None,
        release_id=UNKNOWN_RELEASE,
    ):
        if not isinstance(release_id, str) or release_id != release_id.strip():
            raise ValueError("release_id must be a trimmed string")
        self.retriever = retriever
        self.provider = provider
        self.context_builder = EvidenceContextBuilder()
        self.requirement_retriever = requirement_retriever
        self.count_tokens = count_tokens
        self.trace_dir = Path(trace_dir) if trace_dir else None
        self.release_id = release_id or UNKNOWN_RELEASE
        # Bound shared GPU model execution; all request evidence stays local.
        self._lock = Lock()

    def answer(self, query: str, scope: RetrievalScope | None = None) -> dict:
        if not isinstance(query, str) or not query.strip() or len(query) > 8000:
            raise ValueError("query must contain 1–8000 characters")
        if scope is not None and not isinstance(scope, RetrievalScope):
            raise ValueError("scope must be a RetrievalScope or None")
        query = query.strip()
        # A request without an explicit scope still gets the default policy:
        # legacy v1 chunks (empty metadata) remain eligible, while Schema v2
        # historical/pending_review chunks do not leak into default answers.
        effective_scope = (
            scope
            if scope is not None
            else default_scope(self.release_id or UNKNOWN_RELEASE)
        )
        if self.requirement_retriever is not None:
            return self._workflow_answer(query, scope=effective_scope)
        started = perf_counter()
        # Only shared GPU/model internals and historical trace adapters are locked.
        # Generation, requirements and citations proceed concurrently per request.
        with self._lock:
            hits, _trace, candidates = self.retriever.search_with_trace(
                query, top_k=5, scope=effective_scope
            )
            rerank = candidates["rerank_seconds"]
        retrieval_end = perf_counter()
        context = self.context_builder.build(hits)
        generation_start = perf_counter()
        output = resolve(generate(self.provider, query, context), context)
        output["latency"] = {
            "retrieval_seconds": max(0, retrieval_end - started - rerank),
            "rerank_seconds": rerank,
            "generation_seconds": perf_counter() - generation_start,
            "total_seconds": perf_counter() - started,
        }
        self._attach_scope(output, effective_scope)
        return output

    def _response_release_id(self, scope: RetrievalScope | None) -> str:
        if scope is not None and scope.release_id:
            return scope.release_id
        return self.release_id or UNKNOWN_RELEASE

    def _scope_description(self, scope: RetrievalScope | None) -> dict:
        if scope is not None:
            return scope.describe()
        return default_scope(self.release_id or UNKNOWN_RELEASE).describe()

    def _attach_scope(self, output: dict, scope: RetrievalScope | None) -> None:
        output["release_id"] = self._response_release_id(scope)
        output["retrieval_scope"] = self._scope_description(scope)

    def _workflow_answer(self, query, scope=None):
        from .workflow import run_workflow

        request_id = uuid4().hex
        trace = {"request_id": request_id, "query": query, "calls": []}
        provider = self.provider

        class Recorded:
            def complete(self, messages, tools, **kwargs):
                started = perf_counter()
                response = provider.complete(messages, tools, **kwargs)
                trace["calls"].append(
                    {
                        "messages": [m.to_wire() for m in messages],
                        "response": response.model_dump(),
                        "seconds": perf_counter() - started,
                    }
                )
                return response

        try:
            result, workflow_trace = run_workflow(
                Recorded(),
                self.requirement_retriever,
                query,
                self._lock,
                self.count_tokens,
                audit=trace,
                scope=scope,
            )
            trace.update(workflow_trace)
            result["request_id"] = request_id
            self._attach_scope(result, scope)
            trace["response"] = result
            return result
        except Exception as exc:
            trace["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            try:
                self._save_trace(request_id, trace)
            except OSError:
                logger.exception(
                    "could not persist RAG trace request_id=%s", request_id
                )

    def _save_trace(self, request_id, trace):
        if self.trace_dir is None:
            return
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        path = self.trace_dir / (request_id + ".tmp")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(trace, stream, ensure_ascii=False)
        path.replace(path.with_suffix(".json"))
        # Bound local retention. Only this service's request UUID files qualify.
        with self._lock:
            entries = [
                p
                for p in self.trace_dir.glob("*.json")
                if len(p.stem) == 32 and all(c in "0123456789abcdef" for c in p.stem)
            ]
            entries.sort(key=lambda p: p.stat().st_mtime)
            for old in entries[:-100]:
                old.unlink(missing_ok=True)
