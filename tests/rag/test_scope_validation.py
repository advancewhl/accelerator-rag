"""Scope fields are controlled identities, not arbitrary payload strings."""

from fastapi.testclient import TestClient

from accelerator_rag.rag.api import create_app


class Service:
    def answer(self, query, scope=None):
        return {"query": query, "release_id": "unknown"}


def post(payload):
    with TestClient(create_app(Service())) as client:
        return client.post("/v1/rag/answer", json=payload)


def test_invalid_family_and_revision_ids_are_rejected():
    for scope in (
        {"family_ids": ["Bad Family"]},
        {"revision_ids": ["Bad Revision"]},
    ):
        response = post({"query": "问题", "scope": scope})
        assert response.status_code == 422, scope


def test_invalid_kind_topic_and_usage_are_rejected_with_a_code():
    for scope in (
        {"document_kinds": ["banana"]},
        {"topics": ["not-a-topic"]},
        {"usage_statuses": ["excluded"]},
    ):
        response = post({"query": "问题", "scope": scope})
        assert response.status_code == 422, scope
        assert response.json()["detail"]["code"] == "INVALID_RAG_INPUT"


def test_valid_scope_filters_reach_the_service():
    response = post(
        {
            "query": "问题",
            "scope": {
                "mode": "default",
                "family_ids": ["shine-timing-system-design"],
                "document_kinds": ["operation_manual"],
                "topics": ["timing"],
            },
        }
    )
    assert response.status_code == 200


def test_unknown_scope_field_is_rejected():
    response = post({"query": "问题", "scope": {"unknown": True}})
    assert response.status_code == 422
