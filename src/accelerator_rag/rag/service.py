"""Bounded GPU retrieval; generation and evidence are request local."""

from threading import Lock
from time import perf_counter
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from .answer import generate, resolve
from .context import EvidenceContextBuilder

logger = logging.getLogger(__name__)


class RagService:
    def __init__(
        self,
        retriever,
        provider,
        *,
        requirement_retriever=None,
        count_tokens=None,
        trace_dir=None,
    ):
        self.retriever = retriever
        self.provider = provider
        self.context_builder = EvidenceContextBuilder()
        self.requirement_retriever = requirement_retriever
        self.count_tokens = count_tokens
        self.trace_dir = Path(trace_dir) if trace_dir else None
        # Bound shared GPU model execution; all request evidence stays local.
        self._lock = Lock()

    def answer(self, query: str) -> dict:
        if not isinstance(query, str) or not query.strip() or len(query) > 8000:
            raise ValueError("query must contain 1–8000 characters")
        query = query.strip()
        if self.requirement_retriever is not None:
            return self._workflow_answer(query)
        started = perf_counter()
        # Only shared GPU/model internals and historical trace adapters are locked.
        # Generation, requirements and citations proceed concurrently per request.
        with self._lock:
            hits, _trace, candidates = self.retriever.search_with_trace(query, top_k=5)
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
        return output

    def _workflow_answer(self, query):
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
            )
            trace.update(workflow_trace)
            result["request_id"] = request_id
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
