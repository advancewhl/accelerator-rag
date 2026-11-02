"""Request scope construction, 422 codes and scope propagation."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.rag import service as service_module
from accelerator_rag.rag.api import create_app
from accelerator_rag.rag.runtime import RagRuntime
from accelerator_rag.rag.service import RagService
from accelerator_rag.retrieval.scope import default_scope, version_scope


class RecordingService:
    release_id = "kb-2.0.0"

    def __init__(self):
        self.calls = []

    def answer(self, query, scope=None):
        self.calls.append((query, scope))
        return {"status": "answered", "answer": "ok"}


def scope_for(payload):
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/rag/answer", json=payload)
    assert response.status_code == 200, response.text
    assert len(service.calls) == 1
    return service.calls[0][1]


def test_legacy_request_has_no_explicit_scope():
    assert scope_for({"query": "What is the mode?"}) is None
    assert scope_for({"query": "What is the mode?", "scope": None}) is None
    # An explicit empty scope object still names the running release so the
    # response cannot claim an unrelated release.
    for payload in (
        {"query": "What is the mode?", "scope": {}},
        {"query": "What is the mode?", "scope": {"mode": "default"}},
    ):
        scope = scope_for(payload)
        assert scope.release_id == "kb-2.0.0"
        assert scope.usage_statuses == {"current", "reference"}


def test_requested_release_must_match_the_running_release():
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/rag/answer",
            json={
                "query": "q",
                "scope": {"release_id": "kb-9.9.9"},
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "RELEASE_NOT_FOUND"
    assert not service.calls


def test_default_scope_carries_release_id_without_filters():
    scope = scope_for({"query": "q", "scope": {"release_id": "kb-2.0.0"}})
    assert scope.release_id == "kb-2.0.0"
    assert scope.revision_ids is None
    assert scope.family_ids is None
    assert scope.usage_statuses == {"current", "reference"}
    assert scope.allow_unknown_usage is True


def test_default_scope_applies_explicit_filters():
    scope = scope_for(
        {
            "query": "q",
            "scope": {
                "mode": "default",
                "release_id": "kb-2.0.0",
                "revision_ids": ["rev-a"],
                "family_ids": ["family-a"],
                "usage_statuses": ["current", "historical"],
                "document_kinds": ["operation_manual"],
                "topics": ["ioc"],
            },
        }
    )
    assert scope.release_id == "kb-2.0.0"
    assert scope.revision_ids == {"rev-a"}
    assert scope.family_ids == {"family-a"}
    assert scope.usage_statuses == {"current", "historical"}
    assert scope.document_kinds == {"operation_manual"}
    assert scope.topics == {"ioc"}


def test_version_scope_uses_revision_identity():
    scope = scope_for(
        {
            "query": "q",
            "scope": {
                "mode": "version",
                "release_id": "kb-2.0.0",
                "revision_ids": ["rev-a", "rev-b"],
            },
        }
    )
    assert scope.release_id == "kb-2.0.0"
    assert scope.revision_ids == {"rev-a", "rev-b"}
    assert scope.usage_statuses == {
        "current",
        "historical",
        "reference",
        "pending_review",
    }
    assert scope.allow_unknown_usage is False


def test_version_scope_can_select_a_family():
    scope = scope_for(
        {"query": "q", "scope": {"mode": "version", "family_ids": ["family-a"]}}
    )
    assert scope.revision_ids is None
    assert scope.family_ids == {"family-a"}
    assert scope.usage_statuses == {
        "current",
        "historical",
        "reference",
        "pending_review",
    }
    assert scope.allow_unknown_usage is False


def test_reference_scope_explicitly_allows_pending_review():
    scope = scope_for(
        {
            "query": "q",
            "scope": {
                "mode": "reference",
                "revision_ids": ["rev-a"],
                "release_id": "kb-2.0.0",
            },
        }
    )
    assert scope.revision_ids == {"rev-a"}
    assert "pending_review" in scope.usage_statuses
    assert scope.allow_unknown_usage is False


def test_version_scope_requires_revision_or_family():
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/rag/answer", json={"query": "q", "scope": {"mode": "version"}}
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VERSION_SCOPE_REQUIRED"
    assert not service.calls


def test_compare_mode_is_explicitly_not_implemented():
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/rag/answer",
            json={
                "query": "q",
                "scope": {
                    "mode": "compare",
                    "revision_ids": ["rev-a", "rev-b"],
                },
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "COMPARE_NOT_IMPLEMENTED"
    assert not service.calls


def test_unknown_request_fields_are_still_rejected():
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        top_level = client.post(
            "/v1/rag/answer", json={"query": "q", "unexpected": True}
        )
        nested = client.post(
            "/v1/rag/answer",
            json={"query": "q", "scope": {"unexpected": True}},
        )
    assert top_level.status_code == 422
    assert nested.status_code == 422
    assert not service.calls


def test_revision_ids_must_be_slugs():
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/rag/answer",
            json={
                "query": "q",
                "scope": {"mode": "version", "revision_ids": ["../secret"]},
            },
        )
    assert response.status_code == 422
    assert not service.calls


def test_unqueryable_explicit_usage_status_is_rejected():
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/rag/answer",
            json={"query": "q", "scope": {"usage_statuses": ["excluded"]}},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_RAG_INPUT"
    assert not service.calls


def test_blank_scope_filter_is_rejected_as_invalid_input():
    service = RecordingService()
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/rag/answer",
            json={"query": "q", "scope": {"topics": ["   "]}},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_RAG_INPUT"
    assert not service.calls


def evidence_chunk():
    return KnowledgeChunk(
        chunk_id="chunk-1",
        document_id="rev-a",
        document_title="Design",
        text="The mode is CW.",
        source_path="data/l0_raw/design.pdf",
        document_version="2024",
        language="en",
        category="control_system",
        topic="ioc",
        page_start=1,
        page_end=1,
    )


class RecordingRetriever:
    def __init__(self):
        self.calls = []

    def search_with_trace(self, query, *, top_k, scope):
        self.calls.append((query, top_k, scope))
        hit = RetrievalResult(1, 0.9, evidence_chunk(), "test")
        return [hit], {}, {"rerank_seconds": 0.0}


def fake_generation(monkeypatch):
    monkeypatch.setattr(service_module, "generate", lambda provider, query, context: {})
    monkeypatch.setattr(
        service_module,
        "resolve",
        lambda answer, context: {"status": "answered", "answer": "ok"},
    )


def test_service_passes_scope_to_the_retriever_and_reports_release(monkeypatch):
    fake_generation(monkeypatch)
    retriever = RecordingRetriever()
    service = RagService(retriever, None, release_id="kb-2.0.0")
    scope = version_scope(["rev-a"], release_id="kb-2.0.0")
    result = service.answer("mode?", scope=scope)
    assert retriever.calls == [("mode?", 5, scope)]
    assert result["status"] == "answered"
    assert result["release_id"] == "kb-2.0.0"
    assert result["retrieval_scope"] == scope.describe()


def test_service_falls_back_to_configured_release_without_scope(monkeypatch):
    fake_generation(monkeypatch)
    retriever = RecordingRetriever()
    service = RagService(retriever, None, release_id="kb-2.0.0")
    result = service.answer("mode?")
    assert len(retriever.calls) == 1
    assert retriever.calls[0][1] == 5
    assert retriever.calls[0][2] == default_scope("kb-2.0.0")
    assert result["release_id"] == "kb-2.0.0"
    assert result["retrieval_scope"] == default_scope("kb-2.0.0").describe()


def test_service_workflow_path_receives_scope(monkeypatch):
    seen = {}

    def fake_run_workflow(
        provider, retriever, query, lock, count_tokens, **kwargs
    ):
        seen["scope"] = kwargs.get("scope")
        return {"status": "answered", "answer": "ok"}, {}

    monkeypatch.setattr(
        "accelerator_rag.rag.workflow.run_workflow", fake_run_workflow
    )
    service = RagService(
        None,
        None,
        requirement_retriever=object(),
        count_tokens=len,
        release_id="kb-2.0.0",
    )
    scope = version_scope(["rev-a"], release_id="kb-2.0.0")
    result = service.answer("mode?", scope=scope)
    assert seen["scope"] is scope
    assert result["release_id"] == "kb-2.0.0"
    assert result["retrieval_scope"] == scope.describe()


def test_runtime_forwards_scope_unchanged():
    class Service:
        def __init__(self):
            self.calls = []

        def answer(self, query, scope=None):
            self.calls.append((query, scope))
            return {"status": "answered"}

    runtime = object.__new__(RagRuntime)
    runtime.service = Service()
    scope = version_scope(["rev-a"], release_id="kb-2.0.0")
    assert runtime.answer("mode?", scope=scope) == {"status": "answered"}
    assert runtime.service.calls == [("mode?", scope)]


def test_scope_object_must_be_a_retrieval_scope():
    service = RagService(RecordingRetriever(), None)
    with pytest.raises(ValueError):
        service.answer("mode?", scope=SimpleNamespace())
