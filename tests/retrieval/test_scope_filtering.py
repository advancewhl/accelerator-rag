"""Scope filtering happens before candidate selection in every recall path."""

import json
from threading import Lock

import pytest
from qdrant_client import QdrantClient, models

from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.domain.model import AssistantResponse, ToolCall
from accelerator_rag.rag.retrieval import RequirementRetriever
from accelerator_rag.rag.workflow import run_workflow
from accelerator_rag.retrieval.bm25 import BM25Retriever
from accelerator_rag.retrieval.dense import DenseRetriever
from accelerator_rag.retrieval.dense_reranked import DenseRerankedRetriever
from accelerator_rag.retrieval.index_contract import DenseIndexContract
from accelerator_rag.retrieval.passages import PassageBuilder
from accelerator_rag.retrieval.scope import (
    RetrievalScope,
    default_scope,
    version_scope,
)
from accelerator_rag.storage.qdrant_passages import (
    PassageHit,
    QdrantPassageStore,
    build_scope_filter,
)


def make_chunk(
    chunk_id,
    *,
    document_id=None,
    text="evidence",
    page=1,
    version="2024",
    usage_status="current",
    access_scope="internal",
    family_id="",
    topic="ioc",
    position_kind="",
    section_path="",
    document_ordinal=0,
    approval_status="unknown",
    tags="",
):
    return KnowledgeChunk(
        chunk_id,
        document_id or chunk_id.split(":")[0],
        "SHINE design",
        text,
        "data/l0_raw/design.pdf",
        version,
        "en",
        "control_system",
        topic,
        page,
        page,
        family_id=family_id,
        document_kind="subsystem_design",
        evidence_role="design_target",
        usage_status=usage_status,
        approval_status=approval_status,
        access_scope=access_scope,
        position_kind=position_kind,
        section_path=section_path,
        tags=tags,
        document_ordinal=document_ordinal,
    )


def contract_for(embedder, builder):
    return DenseIndexContract.from_fingerprint(embedder.fingerprint(), builder.contract)


def test_bm25_filters_before_scoring_and_handles_empty_scope():
    current = make_chunk("current-doc:one", text="interlock controller logic")
    historical = make_chunk(
        "historical-doc:one",
        text="controller controller controller interlock",
        usage_status="historical",
    )
    retriever = BM25Retriever([current, historical])

    # The historical parent wins lexically before the scope is applied.
    assert [hit.chunk for hit in retriever.search("controller", top_k=2)] == [
        historical,
        current,
    ]
    # It must not consume a slot and then be dropped after top_k.
    scoped = retriever.search("controller", top_k=1, scope=default_scope())
    assert [hit.chunk for hit in scoped] == [current]
    # An empty eligible set is a normal empty result, not an error.
    assert (
        retriever.search("controller", top_k=3, scope=version_scope(["missing"]))
        == []
    )


def test_bm25_version_scope_can_select_a_historical_revision():
    current = make_chunk("current-doc:one", text="interlock controller logic")
    historical = make_chunk(
        "historical-doc:one",
        text="controller controller controller interlock",
        usage_status="historical",
    )
    retriever = BM25Retriever([current, historical])
    hits = retriever.search(
        "controller", top_k=2, scope=version_scope(["historical-doc"])
    )
    assert [hit.chunk for hit in hits] == [historical]


def test_scope_filter_translates_explicit_axes_and_keeps_default_compatible():
    scope = RetrievalScope(
        revision_ids={"rev-a"},
        family_ids={"family-a"},
        usage_statuses={"current"},
        document_kinds={"operation_manual"},
        evidence_roles={"operating_step"},
        topics={"ioc"},
        access_scopes={"internal"},
        allow_unknown_usage=False,
        allow_unknown_access=False,
    )
    query_filter = build_scope_filter(scope)
    assert isinstance(query_filter, models.Filter)
    assert build_scope_filter(None) is None
    # The default policy is applied server-side too: v2 historical/pending and
    # restricted chunks are excluded, while legacy missing/empty metadata is
    # explicitly admitted by the unknown-field OR branches.
    default_filter = build_scope_filter(default_scope())
    assert default_filter is not None
    assert len(default_filter.must) == 2

    def field_conditions(node):
        for item in list(node.must or []) + list(node.should or []):
            if isinstance(item, models.Filter):
                yield from field_conditions(item)
            elif isinstance(item, models.FieldCondition):
                yield item

    conditions = list(field_conditions(query_filter))
    keys = {condition.key for condition in conditions}
    assert {
        "document_id",
        "family_id",
        "document_kind",
        "evidence_role",
        "topic",
        "usage_status",
        "access_scope",
    } <= keys
    # Strict usage/access: no unknown fallback when both allow flags are false.
    values = {
        condition.match.value
        for condition in conditions
        if isinstance(condition.match, models.MatchValue)
    }
    assert "unknown" not in values


def test_dense_sends_scope_filter_and_returns_only_eligible_parents(
    passage_embedder, monkeypatch
):
    allowed = make_chunk("allowed-doc:one", text="startup interlock guidance")
    historical = make_chunk(
        "historical-doc:one",
        text="startup historical guidance",
        usage_status="historical",
    )
    builder = PassageBuilder(passage_embedder)
    client = QdrantClient(":memory:")
    try:
        store = QdrantPassageStore(
            client, "scope_dense", contract_for(passage_embedder, builder)
        )
        retriever = DenseRetriever(
            passage_embedder, store, passage_builder=builder
        )
        chunks = [allowed, historical]
        retriever.index_corpus(
            chunks, document_ids=[chunk.document_id for chunk in chunks]
        )

        captured = []
        original = client.query_points

        def capture(*args, **kwargs):
            captured.append(kwargs.get("query_filter"))
            return original(*args, **kwargs)

        monkeypatch.setattr(client, "query_points", capture)

        # The default policy is also applied server-side; legacy payloads are
        # admitted by the explicit unknown-field branches, not by skipping the
        # filter.
        default_hits, default_trace, _ = retriever.search_with_trace(
            "startup", top_k=5, scope=default_scope()
        )
        assert captured and all(
            isinstance(item, models.Filter) for item in captured
        )
        assert [hit.chunk.chunk_id for hit in default_hits] == [allowed.chunk_id]
        assert default_trace[0]["scope_applied"] is True

        captured.clear()
        scope = RetrievalScope(
            usage_statuses={"current"}, allow_unknown_usage=False
        )
        hits, trace, _ = retriever.search_with_trace("startup", top_k=5, scope=scope)
        assert captured and all(
            isinstance(item, models.Filter) for item in captured
        )
        assert [hit.chunk.chunk_id for hit in hits] == [allowed.chunk_id]
        assert trace[0]["scope_applied"] is True
        assert trace[0]["scope"]["usage_statuses"] == ["current"]

        # An explicit revision scope must be able to reach the historical
        # revision instead, proving the filter is identity-based.
        captured.clear()
        version = version_scope(["historical-doc"])
        hits, trace, _ = retriever.search_with_trace(
            "startup", top_k=5, scope=version
        )
        assert [hit.chunk.chunk_id for hit in hits] == [historical.chunk_id]
        assert captured and all(
            isinstance(item, models.Filter) for item in captured
        )
    finally:
        client.close()


def test_dense_drops_disallowed_high_scoring_hits_defensively(
    passage_embedder, monkeypatch
):
    allowed = make_chunk("allowed-doc:one", text="startup interlock")
    historical = make_chunk(
        "historical-doc:one", text="startup historical", usage_status="historical"
    )
    builder = PassageBuilder(passage_embedder)
    client = QdrantClient(":memory:")
    try:
        store = QdrantPassageStore(
            client, "scope_fake", contract_for(passage_embedder, builder)
        )
        retriever = DenseRetriever(
            passage_embedder, store, passage_builder=builder
        )
        passages = {
            passage.parent_chunk_id: passage
            for passage in builder.build([allowed, historical])
        }

        def fake_search(vector, limit, *, scope=None):
            assert scope is not None
            return [
                PassageHit(0.99, passages[historical.chunk_id]),
                PassageHit(0.5, passages[allowed.chunk_id]),
            ]

        monkeypatch.setattr(store, "search_passages", fake_search)
        monkeypatch.setattr(
            store, "count_passages", lambda *, scope=None: len(passages)
        )
        scope = RetrievalScope(
            usage_statuses={"current"}, allow_unknown_usage=False
        )
        hits, trace, _ = retriever.search_with_trace("startup", top_k=5, scope=scope)
        assert [hit.chunk.chunk_id for hit in hits] == [allowed.chunk_id]
        assert trace[0]["passage_score"] == pytest.approx(0.5)
    finally:
        client.close()


def test_reranked_gives_both_channels_one_scope_and_only_allowed_winners():
    allowed = make_chunk("allowed-doc:one", text="interlock guidance")
    historical = make_chunk(
        "historical-doc:one", text="historical interlock", usage_status="historical"
    )
    scope = default_scope()

    class FakeDense:
        def __init__(self):
            self.scopes = []

        def search_with_trace(self, query, *, top_k, scope=None):
            self.scopes.append(scope)
            hits = [
                RetrievalResult(1, 0.9, historical, "fake"),
                RetrievalResult(2, 0.5, allowed, "fake"),
            ]
            traces = [
                {
                    "parent_chunk_id": historical.chunk_id,
                    "passage_id": "historical-passage",
                    "passage_excerpt": historical.text,
                },
                {
                    "parent_chunk_id": allowed.chunk_id,
                    "passage_id": "allowed-passage",
                    "passage_excerpt": allowed.text,
                },
            ]
            return hits, traces, {"rerank_seconds": 0}

    class Reranker:
        def score(self, query, texts):
            return [1.0 if text == historical.text else 0.1 for text in texts]

    e5, qwen = FakeDense(), FakeDense()
    retriever = DenseRerankedRetriever(e5, qwen, Reranker())
    hits, trace, candidates = retriever.search_with_trace(
        "interlock", top_k=5, scope=scope
    )
    assert e5.scopes == [scope] and qwen.scopes == [scope]
    assert [hit.chunk for hit in hits] == [allowed]
    assert [row["parent_chunk_id"] for row in trace] == [allowed.chunk_id]
    assert candidates["parent_count"] == 1


def test_same_page_expansion_and_anchors_respect_scope():
    main = make_chunk("rev-a:main", text="controller and converter", page=3)
    allowed_neighbor = make_chunk(
        "rev-a:neighbor", text="local contacts", page=3, usage_status="reference"
    )
    historical_neighbor = make_chunk(
        "rev-a:historical",
        text="obsolete local contacts",
        page=3,
        usage_status="historical",
    )
    other_revision = make_chunk(
        "rev-b:neighbor",
        document_id="rev-b",
        text="other revision contacts",
        page=3,
    )
    disallowed_anchor = make_chunk(
        "rev-a:anchor", text="historical anchor", page=5, usage_status="historical"
    )
    anchor_page_neighbor = make_chunk(
        "rev-a:anchor-neighbor", text="current anchor neighbor", page=5
    )

    class Dense:
        def __init__(self):
            self.scopes = []

        def search_with_trace(self, query, *, top_k, scope=None):
            self.scopes.append(scope)
            return [RetrievalResult(1, 0.9, main, "fake")], [], {
                "rerank_seconds": 0
            }

    class EmptyLexical:
        def __init__(self):
            self.scopes = []

        def search(self, query, *, top_k, scope=None):
            self.scopes.append(scope)
            return []

    class Reranker:
        def score(self, query, texts):
            return [0.5] * len(texts)

    dense, lexical = Dense(), EmptyLexical()
    retriever = RequirementRetriever(
        dense,
        [main, allowed_neighbor, historical_neighbor, other_revision,
         disallowed_anchor, anchor_page_neighbor],
        Reranker(),
    )
    retriever.lexical = lexical
    scope = default_scope()
    results, trace = retriever.retrieve(
        "controller connection",
        ["controller connection"],
        anchors=[RetrievalResult(1, 0.9, disallowed_anchor, "test")],
        scope=scope,
    )

    assert dense.scopes == [scope] and lexical.scopes == [scope]
    assert {hit.chunk.chunk_id for hit in results} == {
        main.chunk_id,
        allowed_neighbor.chunk_id,
    }
    # The disallowed anchor must not pull in its otherwise eligible page.
    assert anchor_page_neighbor.chunk_id not in {
        hit.chunk.chunk_id for hit in results
    }
    assert trace["scope"] == scope.describe()


def test_approval_status_filter_rejects_unknown_and_draft():
    approved = make_chunk("rev-a:approved", approval_status="approved")
    draft = make_chunk("rev-a:draft", approval_status="draft")
    unknown = make_chunk("rev-a:unknown", approval_status="")

    scope = RetrievalScope(approval_statuses=frozenset({"approved"}))
    assert scope.allows(approved)
    assert not scope.allows(draft)
    assert not scope.allows(unknown)
    assert scope.describe()["approval_statuses"] == ["approved"]


def test_tags_and_legacy_series_family_alias():
    chunk = make_chunk(
        "rev-a:tagged",
        family_id="shine-control-operation-manual-timing",
        tags=(
            "series:shine-control-operation-manual-series;"
            "device:timing;batch-2026-11-02"
        ),
    )

    assert RetrievalScope(tags=frozenset({"series:shine-control-operation-manual-series"})).allows(chunk)
    assert RetrievalScope(tags=frozenset({"device:timing"})).allows(chunk)
    assert not RetrievalScope(tags=frozenset({"device:interlock"})).allows(chunk)
    # Old clients still send the pre-split family ID.
    assert RetrievalScope(
        family_ids=frozenset({"shine-control-operation-manual-series"})
    ).allows(chunk)
    assert chunk.tag_list[-1] == "batch-2026-11-02"


def test_paragraph_neighbors_follow_reading_order_not_page_number():
    paragraphs = [
        make_chunk(
            f"rev-a:p{i}",
            text=f"paragraph {i} about timing",
            page=i,
            position_kind="paragraph",
            section_path="2. 定时系统",
            document_ordinal=i,
        )
        for i in range(1, 6)
    ]

    class Dense:
        def search_with_trace(self, query, *, top_k, scope=None):
            return [RetrievalResult(1, 0.9, paragraphs[2], "fake")], [], {
                "rerank_seconds": 0
            }

    class EmptyLexical:
        def search(self, query, *, top_k, scope=None):
            return []

    class Reranker:
        def score(self, query, texts):
            return [0.5] * len(texts)

    retriever = RequirementRetriever(
        Dense(), paragraphs, Reranker()
    )
    retriever.lexical = EmptyLexical()
    results, _trace = retriever.retrieve(
        "timing", ["timing"], scope=default_scope()
    )

    # Each Word paragraph has its own position number; expansion must use the
    # explicit reading order instead of the shared page bucket.
    assert {hit.chunk.chunk_id for hit in results} == {
        paragraph.chunk_id for paragraph in paragraphs
    }


def test_workflow_passes_scope_to_every_retrieval_round():
    class Provider:
        def __init__(self, outputs):
            self.outputs = iter(outputs)

        def complete(self, messages, tools, **kwargs):
            name = tools[0]["function"]["name"]
            expected, output = next(self.outputs)
            assert name == expected
            return AssistantResponse(
                tool_calls=(
                    ToolCall(id="call", name=name, arguments=json.dumps(output)),
                )
            )

    no_evidence = {
        "requirements": [
            {
                "id": "R1",
                "supported": False,
                "span_ids": [],
                "missing": "No trip thresholds.",
            }
        ]
    }
    outputs = [
        (
            "submit_requirements",
            {
                "requirements": [
                    {"id": "R1", "question": "What are the trip thresholds?"}
                ]
            },
        ),
        ("submit_evidence", no_evidence),
        (
            "submit_supplementary_queries",
            {"queries": [{"requirement_id": "R1", "text": "trip thresholds"}]},
        ),
        ("submit_evidence", no_evidence),
    ]

    class Retriever:
        def __init__(self):
            self.scopes = []

        def retrieve(self, query, queries, *, anchors, scope=None):
            self.scopes.append(scope)
            chunk = make_chunk("evidence-doc:one", text="Unrelated evidence.")
            return [RetrievalResult(1, 0.9, chunk, "fake")], {
                "rerank_seconds": 0
            }

    retriever = Retriever()
    scope = default_scope("kb-2.0.0")
    result, trace = run_workflow(
        Provider(outputs),
        retriever,
        "Trip thresholds?",
        Lock(),
        len,
        audit={},
        scope=scope,
    )
    assert result["status"] == "insufficient"
    assert len(retriever.scopes) == 2
    assert all(item is scope for item in retriever.scopes)
    assert trace["scope"] == scope.describe()


def _qdrant_count(chunks, scope):
    """Count stored payloads the server-side scope filter admits."""

    client = QdrantClient(":memory:")
    client.create_collection(
        "scope",
        vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE),
    )
    points = []
    for index, chunk in enumerate(chunks, 1):
        payload = {
            key: value
            for key, value in chunk.__dict__.items()
            if key not in {"chunk_id", "text"}
        }
        points.append(models.PointStruct(id=index, vector=[1.0, 0.0], payload=payload))
    client.upsert("scope", points=points)
    return client.count("scope", count_filter=build_scope_filter(scope)).count


def test_qdrant_family_alias_matches_python_scope():
    split = make_chunk(
        "rev-a:split",
        family_id="shine-control-operation-manual-timing",
        usage_status="reference",
        tags="series:shine-control-operation-manual-series;device:timing",
    )
    other = make_chunk("rev-b:other", family_id="other-family", usage_status="reference")
    scope = RetrievalScope(
        family_ids=frozenset({"shine-control-operation-manual-series"})
    )
    assert scope.allows(split) and not scope.allows(other)
    # Before the fix the vector prefilter admitted 0 of these parents.
    assert _qdrant_count([split, other], scope) == 1


def test_qdrant_prefilters_approval_and_tags_like_python_scope():
    chunks = [
        make_chunk("rev-a:approved", approval_status="approved", tags="device:timing"),
        make_chunk("rev-b:unknown", approval_status="", tags="device:timing"),
        make_chunk("rev-c:draft", approval_status="draft", tags="device:vacuum"),
    ]
    approved = RetrievalScope(approval_statuses=frozenset({"approved"}))
    assert _qdrant_count(chunks, approved) == sum(map(approved.allows, chunks)) == 1
    unknown = RetrievalScope(approval_statuses=frozenset({"unknown"}))
    assert _qdrant_count(chunks, unknown) == sum(map(unknown.allows, chunks)) == 1
    tagged = RetrievalScope(tags=frozenset({"device:timing"}))
    assert _qdrant_count(chunks, tagged) == sum(map(tagged.allows, chunks)) == 2
